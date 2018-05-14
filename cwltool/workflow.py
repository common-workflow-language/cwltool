from __future__ import absolute_import
import copy
import functools
import json
import logging
import random
import tempfile
from collections import namedtuple
from typing import (Any, Callable, Dict, Generator, Iterable, List, Optional,
                    Text, Union, cast)

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
            return Workflow(toolpath_object, eval_timeout, debug, js_console,
                            force_docker_pull, job_script_provider, makeTool,
                            **kwargs)

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
        self.outdir = kwargs.get("outdir")
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
                    _logger.warning(u"[job %s] Notice: scattering over empty input in '%s'.  All outputs will be empty.", step.name, "', '".join(emptyscatter))

                if method == "dotproduct" or method is None:
                    jobs = dotproduct_scatter(step, inputobj, scatter,
                                              cast(  # known bug with mypy
                                                  # https://github.com/python/mypy/issues/797
                                                  Callable[[Any], Any], callback),
                                              mutation_manager, basedir,
                                              **kwargs)
                elif method == "nested_crossproduct":
                    jobs = nested_crossproduct_scatter(step, inputobj,
                                                       scatter, cast(Callable[[Any], Any], callback),
                                                       # known bug in mypy
                                                       # https://github.com/python/mypy/issues/797
                                                       **kwargs)
                elif method == "flat_crossproduct":
                    jobs = cast(Generator,
                                flat_crossproduct_scatter(step, inputobj,
                                                          scatter,
                                                          cast(Callable[[Any], Any],
                                                               # known bug in mypy
                                                               # https://github.com/python/mypy/issues/797
                                                               callback), 0, **kwargs))
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
        self.processStatus = "success"

        if "outdir" in kwargs:
            del kwargs["outdir"]

        for e, i in enumerate(self.tool["inputs"]):
            with SourceLine(self.tool["inputs"], e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                iid = shortname(i["id"])
                if iid in joborder:
                    self.state[i["id"]] = WorkflowStateItem(i, copy.deepcopy(joborder[iid]), "success")
                elif "default" in i:
                    self.state[i["id"]] = WorkflowStateItem(i, copy.deepcopy(i["default"]), "success")
                else:
                    raise WorkflowException(
                        u"Input '%s' not in input object and does not have a default value." % (i["id"]))

        for s in self.steps:
            for out in s.tool["outputs"]:
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
                    except WorkflowException as e:
                        _logger.error(u"[%s] Cannot make job: %s", step.name, e)
                        _logger.debug("", exc_info=True)
                        self.processStatus = "permanentFail"

                if step.iterable:
                    try:
                        for newjob in step.iterable:
                            if kwargs.get("on_error", "stop") == "stop" and self.processStatus != "success":
                                break
                            if newjob:
                                self.made_progress = True
                                yield newjob
                            else:
                                break
                    except WorkflowException as e:
                        _logger.error(u"[%s] Cannot make job: %s", step.name, e)
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
        for n, step in enumerate(self.tool.get("steps", [])):
            try:
                self.steps.append(WorkflowStep(
                    step, n, eval_timeout, debug, js_console,
                    force_docker_pull, job_script_provider, makeTool, **kwargs))
            except validate.ValidationException as v:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.exception("Validation failed at")
                validation_errors.append(v)

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
        wj = WorkflowJob(self, **kwargs)
        yield wj

        kwargs["part_of"] = u"workflow %s" % wj.name
        kwargs["toplevel"] = False

        for w in wj.job(builder.job, output_callbacks, mutation_manager,
                        basedir, **kwargs):
            yield w

    def visit(self, op):
        op(self.tool)
        for s in self.steps:
            s.visit(op)



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
                    enable_dev=kwargs.get("enable_dev", False),
                    strict=kwargs.get("strict", True),
                    fetcher_constructor=kwargs.get("fetcher_constructor"),
                    resolver=kwargs.get("resolver"),
                    overrides=kwargs.get("overrides"))
        except validate.ValidationException as v:
            raise WorkflowException(
                u"Tool definition %s failed validation:\n%s" %
                (toolpath_object["run"], validate.indent(str(v))))

        validation_errors = []
        self.tool = toolpath_object = copy.deepcopy(toolpath_object)
        bound = set()
        for stepfield, toolfield in (("in", "inputs"), ("out", "outputs")):
            toolpath_object[toolfield] = []
            for n, step_entry in enumerate(toolpath_object[stepfield]):
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
                            SourceLine(self.tool["out"], n).makeError(
                                "Workflow step output '%s' does not correspond to" % shortname(step_entry))
                            + "\n" + SourceLine(self.embedded_tool.tool, "outputs").makeError(
                                "  tool output (expected '%s')" % (
                                    "', '".join(
                                        [shortname(tool_entry["id"]) for tool_entry in
                                         self.embedded_tool.tool[toolfield]]))))
                param["id"] = inputid
                param.lc.line = toolpath_object[stepfield].lc.data[n][0]
                param.lc.col = toolpath_object[stepfield].lc.data[n][1]
                param.lc.filename = toolpath_object[stepfield].lc.filename
                toolpath_object[toolfield].append(param)

        missing = []
        for i, tool_entry in enumerate(self.embedded_tool.tool["inputs"]):
            if shortname(tool_entry["id"]) not in bound:
                if "null" not in tool_entry["type"] and "default" not in tool_entry:
                    missing.append(shortname(tool_entry["id"]))

        if missing:
            validation_errors.append(SourceLine(self.tool, "in").makeError(
                "Step is missing required parameter%s '%s'" % ("s" if len(missing) > 1 else "", "', '".join(missing))))

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
                raise validate.ValidationException("Must specify scatterMethod when scattering over multiple inputs")

            inp_map = {i["id"]: i for i in inputparms}
            for s in scatter:
                if s not in inp_map:
                    raise validate.ValidationException(
                        SourceLine(self.tool, "scatter").makeError(u"Scatter parameter '%s' does not correspond to an input parameter of this "
                                                                   u"step, expecting '%s'" % (shortname(s), "', '".join(shortname(k) for k in inp_map.keys()))))

                inp_map[s]["type"] = {"type": "array", "items": inp_map[s]["type"]}

            if self.tool.get("scatterMethod") == "nested_crossproduct":
                nesting = len(scatter)
            else:
                nesting = 1

            for r in range(0, nesting):
                for op in outputparms:
                    op["type"] = {"type": "array", "items": op["type"]}
            self.tool["inputs"] = inputparms
            self.tool["outputs"] = outputparms

    def receive_output(self, output_callback, jobout, processStatus):
        # type: (Callable[...,Any], Dict[Text, Text], Text) -> None
        # _logger.debug("WorkflowStep output from run is %s", jobout)
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
        for i in self.tool["inputs"]:
            p = i["id"]
            field = shortname(p)
            job_order[field] = job_order[i["id"]]
            del job_order[i["id"]]

        try:
            for t in self.embedded_tool.job(job_order,
                                            functools.partial(
                                                self.receive_output,
                                                output_callbacks),
                                            mutation_manager, basedir,
                                            **kwargs):
                yield t
        except WorkflowException:
            _logger.error(u"Exception on step '%s'", kwargs.get("name"))
            raise
        except Exception as e:
            _logger.exception("Unexpected exception")
            raise WorkflowException(Text(e))

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
        for k, v in jobout.items():
            self.dest[k][index] = v

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


def parallel_steps(steps, rc, kwargs):  # type: (List[Generator], ReceiveScatterOutput, Dict[str, Any]) -> Generator
    while rc.completed < rc.total:
        made_progress = False
        for index in range(len(steps)):
            step = steps[index]
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
            except WorkflowException as e:
                _logger.error(u"Cannot make scatter job: %s", e)
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
    l = None  # type: Optional[int]
    for s in scatter_keys:
        if l is None:
            l = len(joborder[s])
        elif l != len(joborder[s]):
            raise WorkflowException("Length of input arrays must be equal when performing dotproduct scatter.")
    assert l is not None

    output = {}  # type: Dict[Text,List[Optional[Text]]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output, l)

    steps = []
    for n in range(0, l):
        jo = copy.copy(joborder)
        for s in scatter_keys:
            jo[s] = joborder[s][n]

        jo = kwargs["postScatterEval"](jo)

        steps.append(process.job(
            jo, functools.partial(rc.receive_scatter_output, n),
            mutation_manager, basedir, **kwargs))

    return parallel_steps(steps, rc, kwargs)


def nested_crossproduct_scatter(process, joborder, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[Text, Any], List[Text], Callable[..., Any], **Any) -> Generator
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    output = {}  # type: Dict[Text, List[Optional[Text]]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output, l)

    steps = []
    for n in range(0, l):
        jo = copy.copy(joborder)
        jo[scatter_key] = joborder[scatter_key][n]

        if len(scatter_keys) == 1:
            jo = kwargs["postScatterEval"](jo)
            steps.append(process.job(jo, functools.partial(rc.receive_scatter_output, n), **kwargs))
        else:
            # known bug with mypy, https://github.com/python/mypy/issues/797
            casted = cast(Callable[[Any], Any], functools.partial(rc.receive_scatter_output, n))
            steps.append(nested_crossproduct_scatter(process, jo,
                                                     scatter_keys[1:],
                                                     casted, **kwargs))

    return parallel_steps(steps, rc, kwargs)


def crossproduct_size(joborder, scatter_keys):
    # type: (Dict[Text, Any], List[Text]) -> int
    scatter_key = scatter_keys[0]
    if len(scatter_keys) == 1:
        sum = len(joborder[scatter_key])
    else:
        sum = 0
        for n in range(0, len(joborder[scatter_key])):
            jo = copy.copy(joborder)
            jo[scatter_key] = joborder[scatter_key][n]
            sum += crossproduct_size(joborder, scatter_keys[1:])
    return sum


def flat_crossproduct_scatter(process,          # WorkflowJobStep
                              joborder,         # Dict[Text, Any]
                              scatter_keys,     # List[Text]
                              output_callback,  # Union[ReceiveScatterOutput, Callable[..., Any]]
                              startindex,       # type: int
                              **kwargs          # type: Any
                             ):  # type: (...) -> Union[List[Generator], Generator]
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    rc = None  # type: Optional[ReceiveScatterOutput]

    if startindex == 0 and not isinstance(output_callback, ReceiveScatterOutput):
        output = {}  # type: Dict[Text, List[Optional[Text]]]
        for i in process.tool["outputs"]:
            output[i["id"]] = [None] * crossproduct_size(joborder, scatter_keys)
        rc = ReceiveScatterOutput(output_callback, output, startindex)
    elif isinstance(output_callback, ReceiveScatterOutput):
        rc = output_callback
    else:
        raise Exception("Unhandled code path. Please report this.")
    assert rc is not None

    steps = []
    put = startindex
    for n in range(0, l):
        jo = copy.copy(joborder)
        jo[scatter_key] = joborder[scatter_key][n]

        if len(scatter_keys) == 1:
            jo = kwargs["postScatterEval"](jo)
            steps.append(process.job(jo, functools.partial(rc.receive_scatter_output, put), **kwargs))
            put += 1
        else:
            add = flat_crossproduct_scatter(process, jo, scatter_keys[1:], rc, put, **kwargs)
            put += len(cast(List[Generator], add))
            steps.extend(add)

    if startindex == 0 and not isinstance(output_callback, ReceiveScatterOutput):
        rc.setTotal(put)
        return parallel_steps(steps, rc, kwargs)
    else:
        return steps
