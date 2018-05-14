from __future__ import absolute_import
import copy
import functools
import json
import logging
import random
import tempfile
from collections import namedtuple
from typing import (Any, Callable, Dict, Generator, Iterable, List, Optional,
                    Text, Tuple, Union, cast)

import schema_salad.validate as validate
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.sourceline import SourceLine, cmap

from . import command_line_tool, expression
from .builder import CONTENT_LIMIT
from .errors import WorkflowException
from .load_tool import load_tool
from .mutation import MutationManager  # pylint: disable=unused-import
from .process import Process, shortname, uniquename, get_overrides
from .stdfsaccess import StdFsAccess
from .utils import aslist, DEFAULT_TMP_PREFIX
from .checker import static_checker, can_assign_src_to_sink, check_types
from .software_requirements import DependenciesConfiguration
import six
from six.moves import range

_logger = logging.getLogger("cwltool")

WorkflowStateItem = namedtuple('WorkflowStateItem', ['parameter', 'value', 'success'])


def defaultMakeTool(toolpath_object,      # type: Dict[Text, Any]
                    eval_timeout,         # type: float
                    debug,                # type: bool
                    js_console,           # type: bool
                    force_docker_pull,    # type: bool
                    job_script_provider,  # type: Optional[DependenciesConfiguration]
                    makeTool,             # type: Callable[..., Process]
                    **kwargs              # type: Any
                   ):
    # type: (...) -> Process
    if not isinstance(toolpath_object, dict):
        raise WorkflowException(u"Not a dict: '%s'" % toolpath_object)
    if "class" in toolpath_object:
        if toolpath_object["class"] == "CommandLineTool":
            return command_line_tool.CommandLineTool(
                toolpath_object, eval_timeout, debug, js_console,
                force_docker_pull, job_script_provider, **kwargs)
        elif toolpath_object["class"] == "ExpressionTool":
            return command_line_tool.ExpressionTool(
                toolpath_object, eval_timeout, debug, js_console,
                force_docker_pull, job_script_provider, **kwargs)
        elif toolpath_object["class"] == "Workflow":
            return Workflow(
                toolpath_object, eval_timeout, debug, js_console,
                force_docker_pull, job_script_provider, makeTool, **kwargs)

    raise WorkflowException(
        u"Missing or invalid 'class' field in %s, expecting one of: CommandLineTool, ExpressionTool, Workflow" %
        toolpath_object["id"])


def findfiles(wo, fn=None):  # type: (Any, List) -> List[Dict[Text, Any]]
    if fn is None:
        fn = []
    if isinstance(wo, dict):
        if wo.get("class") == "File":
            fn.append(wo)
            findfiles(wo.get("secondaryFiles", None), fn)
        else:
            for w in wo.values():
                findfiles(w, fn)
    elif isinstance(wo, list):
        for w in wo:
            findfiles(w, fn)
    return fn


def match_types(sinktype,   # type: Union[List[Text], Text]
                src,        # type: WorkflowStateItem
                iid,        # type: Text
                inputobj,   # type: Dict[Text, Any]
                linkMerge,  # type: Text
                valueFrom   # type: Optional[Text]
               ):  # type: (...) -> bool
    if isinstance(sinktype, list):
        # Sink is union type
        for st in sinktype:
            if match_types(st, src, iid, inputobj, linkMerge, valueFrom):
                return True
    elif isinstance(src.parameter["type"], list):
        # Source is union type
        # Check that at least one source type is compatible with the sink.
        original_types = src.parameter["type"]
        for source_type in original_types:
            src.parameter["type"] = source_type
            match = match_types(
                sinktype, src, iid, inputobj, linkMerge, valueFrom)
            if match:
                src.parameter["type"] = original_types
                return True
        src.parameter["type"] = original_types
        return False
    elif linkMerge:
        if iid not in inputobj:
            inputobj[iid] = []
        if linkMerge == "merge_nested":
            inputobj[iid].append(src.value)
        elif linkMerge == "merge_flattened":
            if isinstance(src.value, list):
                inputobj[iid].extend(src.value)
            else:
                inputobj[iid].append(src.value)
        else:
            raise WorkflowException(u"Unrecognized linkMerge enum '%s'" % linkMerge)
        return True
    elif valueFrom is not None \
            or can_assign_src_to_sink(src.parameter["type"], sinktype) \
            or sinktype == "Any":
        # simply assign the value from state to input
        inputobj[iid] = copy.deepcopy(src.value)
        return True
    return False


def object_from_state(state,                  # Dict[Text, WorkflowStateItem]
                      parms,                  # type: List[Dict[Text, Any]]
                      frag_only,              # type: bool
                      supportsMultipleInput,  # type: bool
                      sourceField,            # type: Text
                      incomplete=False        # type: bool
                     ):  # type: (...) -> Optional[Dict[Text, Any]]
    inputobj = {}  # type: Dict[Text, Any]
    for inp in parms:
        iid = inp["id"]
        if frag_only:
            iid = shortname(iid)
        if sourceField in inp:
            connections = aslist(inp[sourceField])
            if (len(connections) > 1 and
                not supportsMultipleInput):
                raise WorkflowException(
                    "Workflow contains multiple inbound links to a single "
                    "parameter but MultipleInputFeatureRequirement is not "
                    "declared.")
            for src in connections:
                if src in state and state[src] is not None and (state[src].success == "success" or incomplete):
                    if not match_types(
                            inp["type"], state[src], iid, inputobj,
                            inp.get("linkMerge", ("merge_nested"
                                                  if len(connections) > 1 else None)),
                            valueFrom=inp.get("valueFrom")):
                        raise WorkflowException(
                            u"Type mismatch between source '%s' (%s) and "
                            "sink '%s' (%s)" % (src,
                                                state[src].parameter["type"], inp["id"],
                                                inp["type"]))
                elif src not in state:
                    raise WorkflowException(
                        u"Connect source '%s' on parameter '%s' does not "
                        "exist" % (src, inp["id"]))
                elif not incomplete:
                    return None

        if inputobj.get(iid) is None and "default" in inp:
            inputobj[iid] = copy.copy(inp["default"])

        if iid not in inputobj and ("valueFrom" in inp or incomplete):
            inputobj[iid] = None

        if iid not in inputobj:
            raise WorkflowException(u"Value for %s not specified" % (inp["id"]))
    return inputobj


class WorkflowJobStep(object):
    def __init__(self, step):  # type: (Any) -> None
        self.step = step
        self.tool = step.tool
        self.id = step.id
        self.submitted = False
        self.completed = False
        self.iterable = None  # type: Optional[Iterable]
        self.name = uniquename(u"step %s" % shortname(self.id))

    def job(self, joborder, output_callback, mutation_manager, basedir, **kwargs):
        # type: (Dict[Text, Text], functools.partial[None], MutationManager, Text, **Any) -> Generator
        kwargs["part_of"] = self.name
        kwargs["name"] = shortname(self.id)

        _logger.info(u"[%s] start", self.name)

        for j in self.step.job(joborder, output_callback, mutation_manager,
                               basedir, **kwargs):
            yield j


class WorkflowJob(object):
    def __init__(self, workflow, **kwargs):
        # type: (Workflow, **Any) -> None
        self.workflow = workflow
        self.tool = workflow.tool
        self.steps = [WorkflowJobStep(s) for s in workflow.steps]
        self.state = {}  # type: Dict[Text, Optional[WorkflowStateItem]]
        self.processStatus = u""
        self.did_callback = False
        self.made_progress = None  # type: Optional[bool]

        if "outdir" in kwargs:
            self.outdir = kwargs["outdir"]
        else:
            self.outdir = tempfile.mkdtemp(
                prefix=kwargs.get("tmp_outdir_prefix", DEFAULT_TMP_PREFIX))

        self.name = uniquename(u"workflow {}".format(
            kwargs.get("name",
                       shortname(self.workflow.tool.get("id", "embedded")))))

        _logger.debug(
            u"[%s] initialized from %s", self.name,
            self.tool.get("id", "workflow embedded in %s" % kwargs.get("part_of")))

    def do_output_callback(self, final_output_callback):
        # type: (Callable[[Any, Any], Any]) -> None

        supportsMultipleInput = bool(self.workflow.get_requirement("MultipleInputFeatureRequirement")[0])

        try:
            wo = object_from_state(self.state, self.tool["outputs"], True, supportsMultipleInput, "outputSource",
                                   incomplete=True)
        except WorkflowException as e:
            _logger.error(u"[%s] Cannot collect workflow output: %s", self.name, e)
            wo = {}
            self.processStatus = "permanentFail"

        _logger.info(u"[%s] completed %s", self.name, self.processStatus)

        self.did_callback = True

        final_output_callback(wo, self.processStatus)

    def receive_output(self, step, outputparms, final_output_callback, jobout, processStatus):
        # type: (WorkflowJobStep, List[Dict[Text,Text]], Callable[[Any, Any], Any], Dict[Text,Text], Text) -> None

        for i in outputparms:
            if "id" in i:
                if i["id"] in jobout:
                    self.state[i["id"]] = WorkflowStateItem(i, jobout[i["id"]], processStatus)
                else:
                    _logger.error(u"[%s] Output is missing expected field %s", step.name, i["id"])
                    processStatus = "permanentFail"

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(u"[%s] produced output %s", step.name, json.dumps(jobout, indent=4))

        if processStatus != "success":
            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

            _logger.warning(u"[%s] completed %s", step.name, processStatus)
        else:
            _logger.info(u"[%s] completed %s", step.name, processStatus)

        step.completed = True
        self.made_progress = True

        completed = sum(1 for s in self.steps if s.completed)
        if completed == len(self.steps):
            self.do_output_callback(final_output_callback)

    def try_make_job(self,
                     step,                   # type: WorkflowJobStep
                     final_output_callback,  # type: Callable[[Any, Any], Any]
                     mutation_manager,       # type: MutationManager
                     basedir,                # type: Text
                     **kwargs                # type: Any
                    ):  # type: (...) -> Generator

        js_console = kwargs.get("js_console", False)
        debug = kwargs.get("debug", False)
        timeout = kwargs.get("eval_timeout")

        inputparms = step.tool["inputs"]
        outputparms = step.tool["outputs"]

        supportsMultipleInput = bool(self.workflow.get_requirement(
            "MultipleInputFeatureRequirement")[0])

        try:
            inputobj = object_from_state(
                self.state, inputparms, False, supportsMultipleInput, "source")
            if inputobj is None:
                _logger.debug(u"[%s] job step %s not ready", self.name, step.id)
                return

            if step.submitted:
                return

            _logger.debug(u"[%s] starting %s", self.name, step.name)

            callback = functools.partial(self.receive_output, step, outputparms, final_output_callback)

            valueFrom = {
                i["id"]: i["valueFrom"] for i in step.tool["inputs"]
                if "valueFrom" in i}

            loadContents = set(i["id"] for i in step.tool["inputs"]
                               if i.get("loadContents"))

            if len(valueFrom) > 0 and not bool(self.workflow.get_requirement("StepInputExpressionRequirement")[0]):
                raise WorkflowException(
                    "Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements")

            vfinputs = {shortname(k): v for k, v in six.iteritems(inputobj)}

            def postScatterEval(io):
                # type: (Dict[Text, Any]) -> Dict[Text, Any]
                shortio = {shortname(k): v for k, v in six.iteritems(io)}

                fs_access = (kwargs.get("make_fs_access") or StdFsAccess)("")
                for k, v in io.items():
                    if k in loadContents and v.get("contents") is None:
                        with fs_access.open(v["location"], "rb") as f:
                            v["contents"] = f.read(CONTENT_LIMIT)

                def valueFromFunc(k, v):  # type: (Any, Any) -> Any
                    if k in valueFrom:
                        return expression.do_eval(
                            valueFrom[k], shortio, self.workflow.requirements,
                            None, None, {}, context=v, debug=debug, js_console=js_console, timeout=timeout)
                    else:
                        return v

                return {k: valueFromFunc(k, v) for k, v in io.items()}

            if "scatter" in step.tool:
                scatter = aslist(step.tool["scatter"])
                method = step.tool.get("scatterMethod")
                if method is None and len(scatter) != 1:
                    raise WorkflowException("Must specify scatterMethod when scattering over multiple inputs")
                kwargs["postScatterEval"] = postScatterEval

                tot = 1
                emptyscatter = [shortname(s) for s in scatter if len(inputobj[s]) == 0]
                if emptyscatter:
                    _logger.warning(
                        "[job %s] Notice: scattering over empty input in "
                        "'%s'.  All outputs will be empty.", step.name,
                        "', '".join(emptyscatter))

                if method == "dotproduct" or method is None:
                    jobs = dotproduct_scatter(
                        step, inputobj, scatter, callback, mutation_manager,
                        basedir, **kwargs)
                elif method == "nested_crossproduct":
                    jobs = nested_crossproduct_scatter(
                        step, inputobj, scatter, callback, mutation_manager,
                        basedir, **kwargs)
                elif method == "flat_crossproduct":
                    jobs = flat_crossproduct_scatter(
                        step, inputobj, scatter, callback, mutation_manager,
                        basedir, **kwargs)
            else:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(u"[job %s] job input %s", step.name,
                                  json.dumps(inputobj, indent=4))

                inputobj = postScatterEval(inputobj)

                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(u"[job %s] evaluated job input to %s",
                                  step.name, json.dumps(inputobj, indent=4))
                jobs = step.job(inputobj, callback, mutation_manager, basedir,
                                **kwargs)

            step.submitted = True

            for j in jobs:
                yield j
        except WorkflowException:
            raise
        except Exception:
            _logger.exception("Unhandled exception")
            self.processStatus = "permanentFail"
            step.completed = True

    def run(self, **kwargs):
        _logger.info(u"[%s] start", self.name)

    def job(self, joborder, output_callback, mutation_manager, basedir, **kwargs):
        # type: (Dict[Text, Any], Callable[[Any, Any], Any], MutationManager, Text, **Any) -> Generator
        self.state = {}
        self.processStatus = "success"

        if "outdir" in kwargs:
            del kwargs["outdir"]

        for index, inp in enumerate(self.tool["inputs"]):
            with SourceLine(self.tool["inputs"], index, WorkflowException,
                            _logger.isEnabledFor(logging.DEBUG)):
                inp_id = shortname(inp["id"])
                if inp_id in joborder:
                    self.state[inp["id"]] = WorkflowStateItem(
                        inp, copy.deepcopy(joborder[inp_id]), "success")
                elif "default" in inp:
                    self.state[inp["id"]] = WorkflowStateItem(
                        inp, copy.deepcopy(inp["default"]), "success")
                else:
                    raise WorkflowException(
                        u"Input '%s' not in input object and does not have a "
                        " default value." % (inp["id"]))

        for step in self.steps:
            for out in step.tool["outputs"]:
                self.state[out["id"]] = None

        completed = 0
        while completed < len(self.steps):
            self.made_progress = False

            for step in self.steps:
                if kwargs.get("on_error", "stop") == "stop" and self.processStatus != "success":
                    break

                if not step.submitted:
                    try:
                        step.iterable = self.try_make_job(
                            step, output_callback, mutation_manager, basedir,
                            **kwargs)
                    except WorkflowException as exc:
                        _logger.error(u"[%s] Cannot make job: %s", step.name, exc)
                        _logger.debug("", exc_info=True)
                        self.processStatus = "permanentFail"

                if step.iterable:
                    try:
                        for newjob in step.iterable:
                            if kwargs.get("on_error", "stop") == "stop" \
                                    and self.processStatus != "success":
                                break
                            if newjob:
                                self.made_progress = True
                                yield newjob
                            else:
                                break
                    except WorkflowException as exc:
                        _logger.error(u"[%s] Cannot make job: %s", step.name, exc)
                        _logger.debug("", exc_info=True)
                        self.processStatus = "permanentFail"

            completed = sum(1 for s in self.steps if s.completed)

            if not self.made_progress and completed < len(self.steps):
                if self.processStatus != "success":
                    break
                else:
                    yield None

        if not self.did_callback:
            self.do_output_callback(output_callback)


class Workflow(Process):
    def __init__(self,
                 toolpath_object,      # type: Dict[Text, Any]
                 eval_timeout,         # type: float
                 debug,                # type: bool
                 js_console,           # type: bool
                 force_docker_pull,    # type: bool
                 job_script_provider,  # type: Optional[DependenciesConfiguration]
                 makeTool,             # type: Callable[..., Process]
                 **kwargs              # type: Any
                ):  # type: (...) -> None
        super(Workflow, self).__init__(
            toolpath_object, eval_timeout, debug, js_console,
            force_docker_pull, job_script_provider, **kwargs)

        kwargs["requirements"] = self.requirements
        kwargs["hints"] = self.hints

        self.steps = []  # type: List[WorkflowStep]
        validation_errors = []
        for index, step in enumerate(self.tool.get("steps", [])):
            try:
                self.steps.append(WorkflowStep(
                    step, index, eval_timeout, debug, js_console,
                    force_docker_pull, job_script_provider, makeTool, **kwargs))
            except validate.ValidationException as vexc:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.exception("Validation failed at")
                validation_errors.append(vexc)

        if validation_errors:
            raise validate.ValidationException("\n".join(str(v) for v in validation_errors))

        random.shuffle(self.steps)

        # statically validate data links instead of doing it at runtime.
        workflow_inputs = self.tool["inputs"]
        workflow_outputs = self.tool["outputs"]

        step_inputs = []  # type: List[Any]
        step_outputs = []  # type: List[Any]
        for step in self.steps:
            step_inputs.extend(step.tool["inputs"])
            step_outputs.extend(step.tool["outputs"])

        if kwargs.get("do_validate", True):
            static_checker(workflow_inputs, workflow_outputs, step_inputs, step_outputs)


    def job(self,
            job_order,         # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            mutation_manager,  # type: MutationManager
            basedir,           # type: Text
            **kwargs           # type: Any
           ):  # type: (...) -> Generator[Any, None, None]
        builder = self._init_job(job_order, mutation_manager, basedir, **kwargs)
        job = WorkflowJob(self, **kwargs)
        yield job

        kwargs["part_of"] = u"workflow %s" % job.name
        kwargs["toplevel"] = False

        for wjob in job.job(builder.job, output_callbacks, mutation_manager,
                            basedir, **kwargs):
            yield wjob

    def visit(self, op):
        op(self.tool)
        for step in self.steps:
            step.visit(op)



class WorkflowStep(Process):
    def __init__(self,
                 toolpath_object,    # type: Dict[Text, Any]
                 pos,                # type: int
                 eval_timeout,       # type: float
                 debug,              # type: bool
                 js_console,         # type: bool
                 force_docker_pull,  # type: bool
                 job_script_provider,  # type: Optional[DependenciesConfiguration]
                 makeTool,           # type: Callable[..., Process]
                 **kwargs            # type: Any
                ):  # type: (...) -> None
        if "id" in toolpath_object:
            self.id = toolpath_object["id"]
        else:
            self.id = "#step" + Text(pos)

        kwargs["requirements"] = (kwargs.get("requirements", []) +
                                  toolpath_object.get("requirements", []) +
                                  get_overrides(kwargs.get("overrides", []),
                                                self.id).get("requirements", []))
        kwargs["hints"] = kwargs.get("hints", []) + toolpath_object.get("hints", [])

        try:
            if isinstance(toolpath_object["run"], dict):
                self.embedded_tool = makeTool(
                    toolpath_object["run"], eval_timeout, debug, js_console,
                    force_docker_pull, job_script_provider, makeTool, **kwargs)
            else:
                self.embedded_tool = load_tool(
                    toolpath_object["run"], makeTool,
                    eval_timeout, debug, js_console, force_docker_pull,
                    job_script_provider, kwargs,
                    kwargs.get("enable_dev", False),
                    kwargs.get("strict", True),
                    kwargs.get("resolver"),
                    kwargs.get("fetcher_constructor"),
                    kwargs.get("overrides"))
        except validate.ValidationException as vexc:
            raise WorkflowException(
                u"Tool definition %s failed validation:\n%s" %
                (toolpath_object["run"], validate.indent(str(vexc))))

        validation_errors = []
        self.tool = toolpath_object = copy.deepcopy(toolpath_object)
        bound = set()
        for stepfield, toolfield in (("in", "inputs"), ("out", "outputs")):
            toolpath_object[toolfield] = []
            for index, step_entry in enumerate(toolpath_object[stepfield]):
                if isinstance(step_entry, six.string_types):
                    param = CommentedMap()  # type: CommentedMap
                    inputid = step_entry
                else:
                    param = CommentedMap(six.iteritems(step_entry))
                    inputid = step_entry["id"]

                shortinputid = shortname(inputid)
                found = False
                for tool_entry in self.embedded_tool.tool[toolfield]:
                    frag = shortname(tool_entry["id"])
                    if frag == shortinputid:
                        #if the case that the step has a default for a parameter,
                        #we do not want the default of the tool to override it
                        step_default = None
                        if "default" in param and "default" in tool_entry:
                            step_default = param["default"]
                        param.update(tool_entry)
                        param["_tool_entry"] = tool_entry
                        if step_default is not None:
                            param["default"] = step_default
                        found = True
                        bound.add(frag)
                        break
                if not found:
                    if stepfield == "in":
                        param["type"] = "Any"
                    else:
                        validation_errors.append(
                            SourceLine(self.tool["out"], index).makeError(
                                "Workflow step output '%s' does not correspond to"
                                % shortname(step_entry))
                            + "\n" + SourceLine(self.embedded_tool.tool, "outputs").makeError(
                                "  tool output (expected '%s')" % (
                                    "', '".join(
                                        [shortname(tool_entry["id"]) for tool_entry in
                                         self.embedded_tool.tool[toolfield]]))))
                param["id"] = inputid
                param.lc.line = toolpath_object[stepfield].lc.data[index][0]
                param.lc.col = toolpath_object[stepfield].lc.data[index][1]
                param.lc.filename = toolpath_object[stepfield].lc.filename
                toolpath_object[toolfield].append(param)

        missing = []
        for i, tool_entry in enumerate(self.embedded_tool.tool["inputs"]):
            if shortname(tool_entry["id"]) not in bound:
                if "null" not in tool_entry["type"] and "default" not in tool_entry:
                    missing.append(shortname(tool_entry["id"]))

        if missing:
            validation_errors.append(SourceLine(self.tool, "in").makeError(
                "Step is missing required parameter%s '%s'" %
                ("s" if len(missing) > 1 else "", "', '".join(missing))))

        if validation_errors:
            raise validate.ValidationException("\n".join(validation_errors))

        super(WorkflowStep, self).__init__(
            toolpath_object, eval_timeout, debug, js_console,
            force_docker_pull, job_script_provider, **kwargs)

        if self.embedded_tool.tool["class"] == "Workflow":
            (feature, _) = self.get_requirement("SubworkflowFeatureRequirement")
            if not feature:
                raise WorkflowException(
                    "Workflow contains embedded workflow but "
                    "SubworkflowFeatureRequirement not in requirements")

        if "scatter" in self.tool:
            (feature, _) = self.get_requirement("ScatterFeatureRequirement")
            if not feature:
                raise WorkflowException(
                    "Workflow contains scatter but ScatterFeatureRequirement "
                    "not in requirements")

            inputparms = copy.deepcopy(self.tool["inputs"])
            outputparms = copy.deepcopy(self.tool["outputs"])
            scatter = aslist(self.tool["scatter"])

            method = self.tool.get("scatterMethod")
            if method is None and len(scatter) != 1:
                raise validate.ValidationException(
                    "Must specify scatterMethod when scattering over multiple inputs")

            inp_map = {i["id"]: i for i in inputparms}
            for inp in scatter:
                if inp not in inp_map:
                    raise validate.ValidationException(
                        SourceLine(self.tool, "scatter").makeError(
                            "Scatter parameter '%s' does not correspond to "
                            "an input parameter of this step, expecting '%s'"
                            % (shortname(inp), "', '".join(
                                shortname(k) for k in inp_map.keys()))))

                inp_map[inp]["type"] = {"type": "array", "items": inp_map[inp]["type"]}

            if self.tool.get("scatterMethod") == "nested_crossproduct":
                nesting = len(scatter)
            else:
                nesting = 1

            for _ in range(0, nesting):
                for oparam in outputparms:
                    oparam["type"] = {"type": "array", "items": oparam["type"]}
            self.tool["inputs"] = inputparms
            self.tool["outputs"] = outputparms

    def receive_output(self, output_callback, jobout, processStatus):
        # type: (Callable[...,Any], Dict[Text, Text], Text) -> None
        output = {}
        for i in self.tool["outputs"]:
            field = shortname(i["id"])
            if field in jobout:
                output[i["id"]] = jobout[field]
            else:
                processStatus = "permanentFail"
        output_callback(output, processStatus)

    def job(self,
            job_order,         # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            mutation_manager,  # type: MutationManager
            basedir,           # type: Text
            **kwargs           # type: Any
           ):  # type: (...) -> Generator[Any, None, None]
        for inp in self.tool["inputs"]:
            field = shortname(inp["id"])
            job_order[field] = job_order[inp["id"]]
            del job_order[inp["id"]]

        try:
            for tool in self.embedded_tool.job(
                    job_order, functools.partial(self.receive_output, output_callbacks),
                    mutation_manager, basedir, **kwargs):
                yield tool
        except WorkflowException:
            _logger.error(u"Exception on step '%s'", kwargs.get("name"))
            raise
        except Exception as exc:
            _logger.exception("Unexpected exception")
            raise WorkflowException(Text(exc))

    def visit(self, op):
        self.embedded_tool.visit(op)


class ReceiveScatterOutput(object):
    def __init__(self,
                 output_callback,  # type: Callable[..., Any]
                 dest,             # type: Dict[Text, List[Optional[Text]]]
                 total             # type: int
                ):  # type: (...) -> None
        self.dest = dest
        self.completed = 0
        self.processStatus = u"success"
        self.total = total
        self.output_callback = output_callback

    def receive_scatter_output(self, index, jobout, processStatus):
        # type: (int, Dict[Text, Text], Text) -> None
        for key, val in jobout.items():
            self.dest[key][index] = val

        if processStatus != "success":
            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

        self.completed += 1

        if self.completed == self.total:
            self.output_callback(self.dest, self.processStatus)

    def setTotal(self, total):  # type: (int) -> None
        self.total = total
        if self.completed == self.total:
            self.output_callback(self.dest, self.processStatus)


def parallel_steps(steps, rc, kwargs):
    # type: (List[Generator], ReceiveScatterOutput, Dict[str, Any]) -> Generator
    while rc.completed < rc.total:
        made_progress = False
        for index, step in enumerate(steps):
            if kwargs.get("on_error", "stop") == "stop" and rc.processStatus != "success":
                break
            try:
                for j in step:
                    if kwargs.get("on_error", "stop") == "stop" and rc.processStatus != "success":
                        break
                    if j:
                        made_progress = True
                        yield j
                    else:
                        break
            except WorkflowException as exc:
                _logger.error(u"Cannot make scatter job: %s", exc)
                _logger.debug("", exc_info=True)
                rc.receive_scatter_output(index, {}, "permanentFail")
        if not made_progress and rc.completed < rc.total:
            yield None


def dotproduct_scatter(process,           # type: WorkflowJobStep
                       joborder,          # type: Dict[Text, Any]
                       scatter_keys,      # type: List[Text]
                       output_callback,   # type: Callable[..., Any]
                       mutation_manager,  # type: MutationManager
                       basedir,           # type: Text
                       **kwargs           # type: Any
                      ):  # type: (...) -> Generator
    jobl = None  # type: Optional[int]
    for key in scatter_keys:
        if jobl is None:
            jobl = len(joborder[key])
        elif jobl != len(joborder[key]):
            raise WorkflowException(
                "Length of input arrays must be equal when performing "
                "dotproduct scatter.")
    assert jobl is not None

    output = {}  # type: Dict[Text,List[Optional[Text]]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * jobl

    rc = ReceiveScatterOutput(output_callback, output, jobl)

    steps = []
    for index in range(0, jobl):
        sjobo = copy.copy(joborder)
        for key in scatter_keys:
            sjobo[key] = joborder[key][index]

        sjobo = kwargs["postScatterEval"](sjobo)

        steps.append(process.job(
            sjobo, functools.partial(rc.receive_scatter_output, index),
            mutation_manager, basedir, **kwargs))

    return parallel_steps(steps, rc, kwargs)


def nested_crossproduct_scatter(process, joborder, scatter_keys, output_callback,
                                mutation_manager, basedir, **kwargs):
    # type: (WorkflowJobStep, Dict[Text, Any], List[Text], Callable[..., Any], MutationManager, Text, **Any) -> Generator
    scatter_key = scatter_keys[0]
    jobl = len(joborder[scatter_key])
    output = {}  # type: Dict[Text, List[Optional[Text]]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * jobl

    rc = ReceiveScatterOutput(output_callback, output, jobl)

    steps = []
    for index in range(0, jobl):
        sjob = copy.copy(joborder)
        sjob[scatter_key] = joborder[scatter_key][index]

        if len(scatter_keys) == 1:
            sjob = kwargs["postScatterEval"](sjob)
            steps.append(process.job(
                sjob, functools.partial(rc.receive_scatter_output, index),
                mutation_manager, basedir, **kwargs))
        else:
            steps.append(nested_crossproduct_scatter(
                process, sjob, scatter_keys[1:],
                functools.partial(rc.receive_scatter_output, index),
                mutation_manager, basedir, **kwargs))

    return parallel_steps(steps, rc, kwargs)


def crossproduct_size(joborder, scatter_keys):
    # type: (Dict[Text, Any], List[Text]) -> int
    scatter_key = scatter_keys[0]
    if len(scatter_keys) == 1:
        ssum = len(joborder[scatter_key])
    else:
        ssum = 0
        for _ in range(0, len(joborder[scatter_key])):
            ssum += crossproduct_size(joborder, scatter_keys[1:])
    return ssum

def flat_crossproduct_scatter(process,           # type: WorkflowJobStep
                              joborder,          # type: Dict[Text, Any]
                              scatter_keys,      # type: List[Text]
                              output_callback,   # type: Callable[..., Any]
                              mutation_manager,  # type: MutationManager
                              basedir,           # type: Text
                              **kwargs           # type: Any
                             ):  # type: (...) -> Generator
    output = {}  # type: Dict[Text, List[Optional[Text]]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * crossproduct_size(joborder, scatter_keys)
    callback = ReceiveScatterOutput(output_callback, output, 0)
    (steps, total) = _flat_crossproduct_scatter(
        process, joborder, scatter_keys, callback, mutation_manager, basedir,
        0, **kwargs)
    callback.setTotal(total)
    return parallel_steps(steps, callback, kwargs)

def _flat_crossproduct_scatter(process,           # type: WorkflowJobStep
                               joborder,          # type: Dict[Text, Any]
                               scatter_keys,      # type: List[Text]
                               callback,          # type: ReceiveScatterOutput
                               mutation_manager,  # type: MutationManager
                               basedir,           # type: Text
                               startindex,        # type: int
                               **kwargs           # type: Any
                              ):  # type: (...) -> Tuple[List[Generator], int]
    """ Inner loop. """
    scatter_key = scatter_keys[0]
    jobl = len(joborder[scatter_key])
    steps = []
    put = startindex
    for index in range(0, jobl):
        sjob = copy.copy(joborder)
        sjob[scatter_key] = joborder[scatter_key][index]

        if len(scatter_keys) == 1:
            sjob = kwargs["postScatterEval"](sjob)
            steps.append(process.job(
                sjob, functools.partial(callback.receive_scatter_output, put),
                mutation_manager, basedir, **kwargs))
            put += 1
        else:
            (add, _) = _flat_crossproduct_scatter(
                process, sjob, scatter_keys[1:], callback, mutation_manager,
                basedir, put, **kwargs)
            put += len(add)
            steps.extend(add)

    return (steps, put)
