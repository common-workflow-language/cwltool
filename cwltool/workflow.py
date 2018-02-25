from __future__ import absolute_import
import copy
import functools
import json
import logging
import random
import tempfile
from collections import namedtuple
from typing import Any, Callable, Dict, Generator, Iterable, List, Text, Union, cast

import schema_salad.validate as validate
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.sourceline import SourceLine, cmap

from . import command_line_tool, expression
from .errors import WorkflowException
from .load_tool import load_tool
from .process import Process, shortname, uniquename, get_overrides
from .utils import aslist
import six
from six.moves import range

_logger = logging.getLogger("cwltool")

WorkflowStateItem = namedtuple('WorkflowStateItem', ['parameter', 'value', 'success'])


def defaultMakeTool(toolpath_object,  # type: Dict[Text, Any]
                    **kwargs  # type: Any
                   ):
    # type: (...) -> Process
    if not isinstance(toolpath_object, dict):
        raise WorkflowException(u"Not a dict: '%s'" % toolpath_object)
    if "class" in toolpath_object:
        if toolpath_object["class"] == "CommandLineTool":
            return command_line_tool.CommandLineTool(toolpath_object, **kwargs)
        elif toolpath_object["class"] == "ExpressionTool":
            return command_line_tool.ExpressionTool(toolpath_object, **kwargs)
        elif toolpath_object["class"] == "Workflow":
            return Workflow(toolpath_object, **kwargs)

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


def match_types(sinktype, src, iid, inputobj, linkMerge, valueFrom):
    # type: (Union[List[Text],Text], WorkflowStateItem, Text, Dict[Text, Any], Text, Text) -> bool
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
    elif valueFrom is not None or can_assign_src_to_sink(src.parameter["type"], sinktype) or sinktype == "Any":
        # simply assign the value from state to input
        inputobj[iid] = copy.deepcopy(src.value)
        return True
    return False


def check_types(srctype, sinktype, linkMerge, valueFrom):
    # type: (Any, Any, Text, Text) -> Text
    """Check if the source and sink types are "pass", "warning", or "exception".
    """

    if valueFrom:
        return "pass"
    elif not linkMerge:
        if can_assign_src_to_sink(srctype, sinktype, strict=True):
            return "pass"
        elif can_assign_src_to_sink(srctype, sinktype, strict=False):
            return "warning"
        else:
            return "exception"
    elif linkMerge == "merge_nested":
        return check_types({"items": srctype, "type": "array"}, sinktype, None, None)
    elif linkMerge == "merge_flattened":
        return check_types(merge_flatten_type(srctype), sinktype, None, None)
    else:
        raise WorkflowException(u"Unrecognized linkMerge enu_m '%s'" % linkMerge)


def merge_flatten_type(src):
    # type: (Any) -> Any
    """Return the merge flattened type of the source type
    """

    if isinstance(src, list):
        return [merge_flatten_type(t) for t in src]
    elif isinstance(src, dict) and src.get("type") == "array":
        return src
    else:
        return {"items": src, "type": "array"}


def can_assign_src_to_sink(src, sink, strict=False):  # type: (Any, Any, bool) -> bool
    """Check for identical type specifications, ignoring extra keys like inputBinding.

    src: admissible source types
    sink: admissible sink types

    In non-strict comparison, at least one source type must match one sink type.
    In strict comparison, all source types must match at least one sink type.
    """

    if src == "Any" or sink == "Any":
        return True
    if isinstance(src, dict) and isinstance(sink, dict):
        if src["type"] == "array" and sink["type"] == "array":
            return can_assign_src_to_sink(src["items"], sink["items"], strict)
        elif src["type"] == "record" and sink["type"] == "record":
            return _compare_records(src, sink, strict)
        return False
    elif isinstance(src, list):
        if strict:
            for t in src:
                if not can_assign_src_to_sink(t, sink):
                    return False
            return True
        else:
            for t in src:
                if can_assign_src_to_sink(t, sink):
                    return True
            return False
    elif isinstance(sink, list):
        for t in sink:
            if can_assign_src_to_sink(src, t):
                return True
        return False
    else:
        return src == sink


def _compare_records(src, sink, strict=False):
    # type: (Dict[Text, Any], Dict[Text, Any], bool) -> bool
    """Compare two records, ensuring they have compatible fields.

    This handles normalizing record names, which will be relative to workflow
    step, so that they can be compared.
    """

    def _rec_fields(rec):  # type: (Dict[Text, Any]) -> Dict[Text, Any]
        out = {}
        for field in rec["fields"]:
            name = shortname(field["name"])
            out[name] = field["type"]
        return out

    srcfields = _rec_fields(src)
    sinkfields = _rec_fields(sink)
    for key in six.iterkeys(sinkfields):
        if (not can_assign_src_to_sink(
                srcfields.get(key, "null"), sinkfields.get(key, "null"), strict)
            and sinkfields.get(key) is not None):
            _logger.info("Record comparison failure for %s and %s\n"
                         "Did not match fields for %s: %s and %s" %
                         (src["name"], sink["name"], key, srcfields.get(key),
                          sinkfields.get(key)))
            return False
    return True


def object_from_state(state, parms, frag_only, supportsMultipleInput, sourceField, incomplete=False):
    # type: (Dict[Text, WorkflowStateItem], List[Dict[Text, Any]], bool, bool, Text, bool) -> Dict[Text, Any]
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
        self.iterable = None  # type: Iterable
        self.name = uniquename(u"step %s" % shortname(self.id))

    def job(self, joborder, output_callback, **kwargs):
        # type: (Dict[Text, Text], functools.partial[None], **Any) -> Generator
        kwargs["part_of"] = self.name
        kwargs["name"] = shortname(self.id)

        _logger.info(u"[%s] start", self.name)

        for j in self.step.job(joborder, output_callback, **kwargs):
            yield j


class WorkflowJob(object):
    def __init__(self, workflow, **kwargs):
        # type: (Workflow, **Any) -> None
        self.workflow = workflow
        self.tool = workflow.tool
        self.steps = [WorkflowJobStep(s) for s in workflow.steps]
        self.state = None  # type: Dict[Text, WorkflowStateItem]
        self.processStatus = None  # type: Text
        self.did_callback = False

        if "outdir" in kwargs:
            self.outdir = kwargs["outdir"]
        elif "tmp_outdir_prefix" in kwargs:
            self.outdir = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"])
        else:
            # tmp_outdir_prefix defaults to tmp, so this is unlikely to be used
            self.outdir = tempfile.mkdtemp()

        self.name = uniquename(u"workflow %s" % kwargs.get("name", shortname(self.workflow.tool.get("id", "embedded"))))

        _logger.debug(u"[%s] initialized from %s", self.name,
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

    def try_make_job(self, step, final_output_callback, **kwargs):
        # type: (WorkflowJobStep, Callable[[Any, Any], Any], **Any) -> Generator

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

            if len(valueFrom) > 0 and not bool(self.workflow.get_requirement("StepInputExpressionRequirement")[0]):
                raise WorkflowException(
                    "Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements")

            vfinputs = {shortname(k): v for k, v in six.iteritems(inputobj)}

            def postScatterEval(io):
                # type: (Dict[Text, Any]) -> Dict[Text, Any]
                shortio = {shortname(k): v for k, v in six.iteritems(io)}

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
                                                  Callable[[Any], Any], callback), **kwargs)
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
                    _logger.debug(u"[job %s] job input %s", step.name, json.dumps(inputobj, indent=4))

                inputobj = postScatterEval(inputobj)

                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(u"[job %s] evaluated job input to %s", step.name, json.dumps(inputobj, indent=4))
                jobs = step.job(inputobj, callback, **kwargs)

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

    def job(self, joborder, output_callback, **kwargs):
        # type: (Dict[Text, Any], Callable[[Any, Any], Any], **Any) -> Generator
        self.state = {}
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
                        step.iterable = self.try_make_job(step, output_callback, **kwargs)
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
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[Text, Any], **Any) -> None
        super(Workflow, self).__init__(toolpath_object, **kwargs)

        kwargs["requirements"] = self.requirements
        kwargs["hints"] = self.hints

        makeTool = kwargs.get("makeTool")
        self.steps = []  # type: List[WorkflowStep]
        validation_errors = []
        for n, step in enumerate(self.tool.get("steps", [])):
            try:
                self.steps.append(WorkflowStep(step, n, **kwargs))
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

        static_checker(workflow_inputs, workflow_outputs, step_inputs, step_outputs)


    def job(self,
            job_order,  # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            **kwargs  # type: Any
            ):
        # type: (...) -> Generator[Any, None, None]
        builder = self._init_job(job_order, **kwargs)
        wj = WorkflowJob(self, **kwargs)
        yield wj

        kwargs["part_of"] = u"workflow %s" % wj.name

        for w in wj.job(builder.job, output_callbacks, **kwargs):
            yield w

    def visit(self, op):
        op(self.tool)
        for s in self.steps:
            s.visit(op)


def static_checker(workflow_inputs, workflow_outputs, step_inputs, step_outputs):
    # type: (List[Dict[Text, Any]], List[Dict[Text, Any]], List[Dict[Text, Any]], List[Dict[Text, Any]]) -> None
    """Check if all source and sink types of a workflow are compatible before run time.
    """

    # source parameters: workflow_inputs and step_outputs
    # sink parameters: step_inputs and workflow_outputs

    # make a dictionary of source parameters, indexed by the "id" field
    src_parms = workflow_inputs + step_outputs
    src_dict = {}
    for parm in src_parms:
        src_dict[parm["id"]] = parm

    step_inputs_val = check_all_types(src_dict, step_inputs, "source")
    workflow_outputs_val = check_all_types(src_dict, workflow_outputs, "outputSource")

    warnings = step_inputs_val["warning"] + workflow_outputs_val["warning"]
    exceptions = step_inputs_val["exception"] + workflow_outputs_val["exception"]

    warning_msgs = []
    exception_msgs = []
    for warning in warnings:
        src = warning.src
        sink = warning.sink
        linkMerge = warning.linkMerge
        msg = SourceLine(src, "type").makeError(
            "Source '%s' of type %s is partially incompatible"
            % (shortname(src["id"]), json.dumps(src["type"]))) + "\n" + \
            SourceLine(sink, "type").makeError(
            "  with sink '%s' of type %s"
            % (shortname(sink["id"]), json.dumps(sink["type"])))
        if linkMerge:
            msg += "\n" + SourceLine(sink).makeError("  source has linkMerge method %s" % linkMerge)
        warning_msgs.append(msg)
    for exception in exceptions:
        src = exception.src
        sink = exception.sink
        linkMerge = exception.linkMerge
        msg = SourceLine(src, "type").makeError(
            "Source '%s' of type %s is incompatible"
            % (shortname(src["id"]), json.dumps(src["type"]))) + "\n" + \
            SourceLine(sink, "type").makeError(
            "  with sink '%s' of type %s"
            % (shortname(sink["id"]), json.dumps(sink["type"])))
        if linkMerge:
            msg += "\n" + SourceLine(sink).makeError("  source has linkMerge method %s" % linkMerge)
        exception_msgs.append(msg)

    for sink in step_inputs:
        if ('null' != sink["type"] and 'null' not in sink["type"]
            and "source" not in sink and "default" not in sink and "valueFrom" not in sink):
            msg = SourceLine(sink).makeError(
                "Required parameter '%s' does not have source, default, or valueFrom expression"
                % shortname(sink["id"]))
            exception_msgs.append(msg)

    all_warning_msg = "\n".join(warning_msgs)
    all_exception_msg = "\n".join(exception_msgs)

    if warnings:
        _logger.warning("Workflow checker warning:\n%s" % all_warning_msg)
    if exceptions:
        raise validate.ValidationException(all_exception_msg)


SrcSink = namedtuple("SrcSink", ["src", "sink", "linkMerge"])

def check_all_types(src_dict, sinks, sourceField):
    # type: (Dict[Text, Any], List[Dict[Text, Any]], Text) -> Dict[Text, List[SrcSink]]
    # sourceField is either "soure" or "outputSource"
    """Given a list of sinks, check if their types match with the types of their sources.
    """

    validation = {"warning": [], "exception": []}  # type: Dict[Text, List[SrcSink]]
    for sink in sinks:
        if sourceField in sink:
            valueFrom = sink.get("valueFrom")
            if isinstance(sink[sourceField], list):
                srcs_of_sink = [src_dict[parm_id] for parm_id in sink[sourceField]]
                linkMerge = sink.get("linkMerge", ("merge_nested"
                                                   if len(sink[sourceField]) > 1 else None))
            else:
                parm_id = sink[sourceField]
                srcs_of_sink = [src_dict[parm_id]]
                linkMerge = None
            for src in srcs_of_sink:
                check_result = check_types(src["type"], sink["type"], linkMerge, valueFrom)
                if check_result == "warning":
                    validation["warning"].append(SrcSink(src, sink, linkMerge))
                elif check_result == "exception":
                    validation["exception"].append(SrcSink(src, sink, linkMerge))
    return validation


class WorkflowStep(Process):
    def __init__(self, toolpath_object, pos, **kwargs):
        # type: (Dict[Text, Any], int, **Any) -> None
        if "id" in toolpath_object:
            self.id = toolpath_object["id"]
        else:
            self.id = "#step" + Text(pos)

        kwargs["requirements"] = (kwargs.get("requirements", []) +
                                  toolpath_object.get("requirements", []) +
                                  get_overrides(kwargs.get("overrides", []), self.id).get("requirements", []))
        kwargs["hints"] = kwargs.get("hints", []) + toolpath_object.get("hints", [])

        try:
            if isinstance(toolpath_object["run"], dict):
                self.embedded_tool = kwargs.get("makeTool")(toolpath_object["run"], **kwargs)
            else:
                self.embedded_tool = load_tool(
                    toolpath_object["run"], kwargs.get("makeTool"), kwargs,
                    enable_dev=kwargs.get("enable_dev"),
                    strict=kwargs.get("strict"),
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

        super(WorkflowStep, self).__init__(toolpath_object, **kwargs)

        if self.embedded_tool.tool["class"] == "Workflow":
            (feature, _) = self.get_requirement("SubworkflowFeatureRequirement")
            if not feature:
                raise WorkflowException(
                    "Workflow contains embedded workflow but SubworkflowFeatureRequirement not in requirements")

        if "scatter" in self.tool:
            (feature, _) = self.get_requirement("ScatterFeatureRequirement")
            if not feature:
                raise WorkflowException("Workflow contains scatter but ScatterFeatureRequirement not in requirements")

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
            job_order,  # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            **kwargs  # type: Any
            ):
        # type: (...) -> Generator[Any, None, None]
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
    def __init__(self, output_callback, dest):
        # type: (Callable[..., Any], Dict[Text,List[Text]]) -> None
        self.dest = dest
        self.completed = 0
        self.processStatus = u"success"
        self.total = None  # type: int
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


def dotproduct_scatter(process, joborder, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[Text, Any], List[Text], Callable[..., Any], **Any) -> Generator
    l = None
    for s in scatter_keys:
        if l is None:
            l = len(joborder[s])
        elif l != len(joborder[s]):
            raise WorkflowException("Length of input arrays must be equal when performing dotproduct scatter.")

    output = {}  # type: Dict[Text,List[Text]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output)

    steps = []
    for n in range(0, l):
        jo = copy.copy(joborder)
        for s in scatter_keys:
            jo[s] = joborder[s][n]

        jo = kwargs["postScatterEval"](jo)

        steps.append(process.job(jo, functools.partial(rc.receive_scatter_output, n), **kwargs))

    rc.setTotal(l)

    return parallel_steps(steps, rc, kwargs)


def nested_crossproduct_scatter(process, joborder, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[Text, Any], List[Text], Callable[..., Any], **Any) -> Generator
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    output = {}  # type: Dict[Text,List[Text]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output)

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

    rc.setTotal(l)

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


def flat_crossproduct_scatter(process, joborder, scatter_keys, output_callback, startindex, **kwargs):
    # type: (WorkflowJobStep, Dict[Text, Any], List[Text], Union[ReceiveScatterOutput,Callable[..., Any]], int, **Any) -> Union[List[Generator], Generator]
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    rc = None  # type: ReceiveScatterOutput

    if startindex == 0 and not isinstance(output_callback, ReceiveScatterOutput):
        output = {}  # type: Dict[Text,List[Text]]
        for i in process.tool["outputs"]:
            output[i["id"]] = [None] * crossproduct_size(joborder, scatter_keys)
        rc = ReceiveScatterOutput(output_callback, output)
    elif isinstance(output_callback, ReceiveScatterOutput):
        rc = output_callback
    else:
        raise Exception("Unhandled code path. Please report this.")

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
