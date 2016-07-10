from . import job
from . import draft2tool
from .utils import aslist
from .process import Process, get_feature, empty_subtree, shortname, uniquename
from .errors import WorkflowException
import copy
import logging
import random
import os
from collections import namedtuple
import functools
import schema_salad.validate as validate
import urlparse
import tempfile
import shutil
import json
import schema_salad
from . import expression
from .load_tool import load_tool
from typing import Iterable, List, Callable, Any, Union, Generator, cast

_logger = logging.getLogger("cwltool")

WorkflowStateItem = namedtuple('WorkflowStateItem', ['parameter', 'value'])

def defaultMakeTool(toolpath_object, **kwargs):
    # type: (Dict[str, Any], **Any) -> Process
    if not isinstance(toolpath_object, dict):
        raise WorkflowException(u"Not a dict: `%s`" % toolpath_object)
    if "class" in toolpath_object:
        if toolpath_object["class"] == "CommandLineTool":
            return draft2tool.CommandLineTool(toolpath_object, **kwargs)
        elif toolpath_object["class"] == "ExpressionTool":
            return draft2tool.ExpressionTool(toolpath_object, **kwargs)
        elif toolpath_object["class"] == "Workflow":
            return Workflow(toolpath_object, **kwargs)

    raise WorkflowException(u"Missing or invalid 'class' field in %s, expecting one of: CommandLineTool, ExpressionTool, Workflow" % toolpath_object["id"])

def findfiles(wo, fn=None):  # type: (Any, List) -> List[Dict[str, Any]]
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
    # type: (Union[List[str],str], WorkflowStateItem, str, Dict[unicode, Any], str, str) -> bool
    if isinstance(sinktype, list):
        # Sink is union type
        for st in sinktype:
            if match_types(st, src, iid, inputobj, linkMerge, valueFrom):
                return True
    elif isinstance(src.parameter["type"], list):
        # Source is union type
        # Check that every source type is compatible with the sink.
        for st in src.parameter["type"]:
            srccopy = copy.deepcopy(src)
            srccopy.parameter["type"] = st
            if not match_types(st, srccopy, iid, inputobj, linkMerge, valueFrom):
                return False
        return True
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

def can_assign_src_to_sink(src, sink):  # type: (Any, Any) -> bool
    """Check for identical type specifications, ignoring extra keys like inputBinding.
    """
    if sink == "Any":
        return True
    if isinstance(src, dict) and isinstance(sink, dict):
        if src["type"] == "array" and sink["type"] == "array":
            return can_assign_src_to_sink(src["items"], sink["items"])
        elif src["type"] == "record" and sink["type"] == "record":
            return _compare_records(src, sink)
    elif isinstance(src, list):
        for t in src:
            if can_assign_src_to_sink(t, sink):
                return True
    elif isinstance(sink, list):
        for t in sink:
            if can_assign_src_to_sink(src, t):
                return True
    else:
        return src == sink
    return False

def _compare_records(src, sink):
    """Compare two records, ensuring they have compatible fields.

    This handles normalizing record names, which will be relative to workflow
    step, so that they can be compared.
    """
    def _rec_fields(rec):
        out = {}
        for field in rec["fields"]:
            name = shortname(field["name"])
            out[name] = field["type"]
        return out

    srcfields = _rec_fields(src)
    sinkfields = _rec_fields(sink)
    for key in sinkfields.iterkeys():
        if not can_assign_src_to_sink(srcfields.get(key, "null"), sinkfields.get(key, "null")) and sinkfields.get(key) is not None:
            _logger.info("Record comparison failure for %s and %s\n"
                         "Did not match fields for %s: %s and %s" %
                         (src["name"], sink["name"], key, srcfields.get(key), sinkfields.get(key)))
            return False
    return True

def object_from_state(state, parms, frag_only, supportsMultipleInput, sourceField):
    # type: (Dict[unicode, WorkflowStateItem], List[Dict[unicode, Any]], bool, bool, unicode) -> Dict[unicode, Any]
    inputobj = {}  # type: Dict[unicode, Any]
    for inp in parms:
        iid = inp["id"]
        if frag_only:
            iid = shortname(iid)
        if sourceField in inp:
            if (isinstance(inp[sourceField], list) and not
                    supportsMultipleInput):
                raise WorkflowException(
                        "Workflow contains multiple inbound links to a single "
                        "parameter but MultipleInputFeatureRequirement is not "
                        "declared.")
            connections = aslist(inp[sourceField])
            for src in connections:
                if src in state and state[src] is not None:
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
                else:
                    return None
        elif "default" in inp:
            inputobj[iid] = inp["default"]
        elif "valueFrom" in inp:
            inputobj[iid] = None
        else:
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
        # type: (Dict[unicode, unicode], functools.partial[None], **Any) -> Generator
        kwargs["part_of"] = self.name
        kwargs["name"] = shortname(self.id)
        for j in self.step.job(joborder, output_callback, **kwargs):
            yield j


class WorkflowJob(object):

    def __init__(self, workflow, **kwargs):
        # type: (Workflow, **Any) -> None
        self.workflow = workflow
        self.tool = workflow.tool
        self.steps = [WorkflowJobStep(s) for s in workflow.steps]
        self.id = workflow.tool["id"]
        self.state = None  # type: Dict[unicode, WorkflowStateItem]
        self.processStatus = None  # type: str
        if "outdir" in kwargs:
            self.outdir = kwargs["outdir"]
        elif "tmp_outdir_prefix" in kwargs:
            self.outdir = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"])
        else:
            # tmp_outdir_prefix defaults to tmp, so this is unlikely to be used
            self.outdir = tempfile.mkdtemp()

        self.name = uniquename(u"workflow %s" % kwargs.get("name", shortname(self.workflow.tool["id"])))

        _logger.debug(u"[%s] initialized step from %s", self.name, self.tool["id"])

    def receive_output(self, step, outputparms, jobout, processStatus):
        # type: (WorkflowJobStep, List[Dict[str,str]], Dict[str,str], str) -> None
        for i in outputparms:
            if "id" in i:
                if i["id"] in jobout:
                    self.state[i["id"]] = WorkflowStateItem(i, jobout[i["id"]])
                else:
                    _logger.error(u"Output is missing expected field %s" % i["id"])
                    processStatus = "permanentFail"

        _logger.debug(u"[%s] produced output %s", step.name, json.dumps(jobout, indent=4))

        if processStatus != "success":
            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

            _logger.warn(u"[%s] completion status is %s", step.name, processStatus)
        else:
            _logger.info(u"[%s] completion status is %s", step.name, processStatus)

        step.completed = True

    def try_make_job(self, step, **kwargs):
        # type: (WorkflowJobStep, **Any) -> Generator
        inputparms = step.tool["inputs"]
        outputparms = step.tool["outputs"]

        supportsMultipleInput = bool(self.workflow.get_requirement(
            "MultipleInputFeatureRequirement")[0])

        try:
            inputobj = object_from_state(
                    self.state, inputparms, False, supportsMultipleInput,
                    "source")
            if inputobj is None:
                _logger.debug(u"[%s] job step %s not ready", self.name, step.id)
                return

            if step.submitted:
                return

            _logger.debug(u"[%s] starting %s", self.name, step.name)

            callback = functools.partial(self.receive_output, step, outputparms)

            valueFrom = {
                    i["id"]: i["valueFrom"] for i in step.tool["inputs"]
                    if "valueFrom" in i}

            if len(valueFrom) > 0 and not bool(self.workflow.get_requirement("StepInputExpressionRequirement")[0]):
                raise WorkflowException("Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements")

            vfinputs = {shortname(k): v for k,v in inputobj.iteritems()}
            def postScatterEval(io):
                # type: (Dict[unicode, Any]) -> Dict[unicode, Any]
                shortio = {shortname(k): v for k,v in io.iteritems()}
                def valueFromFunc(k, v):  # type: (Any, Any) -> Any
                    if k in valueFrom:
                        return expression.do_eval(
                                valueFrom[k], shortio, self.workflow.requirements,
                                None, None, {}, context=v)
                    else:
                        return v
                return {k: valueFromFunc(k, v) for k,v in io.items()}

            if "scatter" in step.tool:
                scatter = aslist(step.tool["scatter"])
                method = step.tool.get("scatterMethod")
                if method is None and len(scatter) != 1:
                    raise WorkflowException("Must specify scatterMethod when scattering over multiple inputs")
                kwargs["postScatterEval"] = postScatterEval

                if method == "dotproduct" or method is None:
                    jobs = dotproduct_scatter(step, inputobj, scatter,
                                              cast(  # known bug with mypy
                                                  # https://github.com/python/mypy/issues/797
                                                  Callable[[Any], Any],callback), **kwargs)
                elif method == "nested_crossproduct":
                    jobs = nested_crossproduct_scatter(step, inputobj,
                            scatter, cast(Callable[[Any], Any], callback),
                            # known bug in mypy
                            # https://github.com/python/mypy/issues/797
                            **kwargs)
                elif method == "flat_crossproduct":
                    jobs = flat_crossproduct_scatter(step, inputobj,
                                                     scatter,
                                                     cast(Callable[[Any], Any],
                                                         # known bug in mypy
                                                         # https://github.com/python/mypy/issues/797
                                                         callback), 0, **kwargs)
            else:
                _logger.debug(u"[job %s] job input %s", step.name, json.dumps(inputobj, indent=4))
                inputobj = postScatterEval(inputobj)
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
        _logger.debug(u"[%s] workflow starting", self.name)

    def job(self, joborder, output_callback, **kwargs):
        # type: (Dict[unicode, Any], Callable[[Any, Any], Any], **Any) -> Generator[WorkflowJob, None, None]
        self.state = {}
        self.processStatus = "success"

        if "outdir" in kwargs:
            del kwargs["outdir"]

        for i in self.tool["inputs"]:
            iid = shortname(i["id"])
            if iid in joborder:
                self.state[i["id"]] = WorkflowStateItem(i, copy.deepcopy(joborder[iid]))
            elif "default" in i:
                self.state[i["id"]] = WorkflowStateItem(i, copy.deepcopy(i["default"]))
            else:
                raise WorkflowException(u"Input '%s' not in input object and does not have a default value." % (i["id"]))

        for s in self.steps:
            for out in s.tool["outputs"]:
                self.state[out["id"]] = None

        completed = 0
        while completed < len(self.steps) and self.processStatus == "success":
            made_progress = False

            for step in self.steps:
                if kwargs["on_error"] == "stop" and self.processStatus != "success":
                    break

                if not step.submitted:
                    step.iterable = self.try_make_job(step, **kwargs)

                if step.iterable:
                    for newjob in step.iterable:
                        if kwargs["on_error"] == "stop" and self.processStatus != "success":
                            break
                        if newjob:
                            made_progress = True
                            yield newjob
                        else:
                            break

            completed = sum(1 for s in self.steps if s.completed)

            if not made_progress and completed < len(self.steps):
                yield None

        supportsMultipleInput = bool(self.workflow.get_requirement("MultipleInputFeatureRequirement")[0])

        wo = object_from_state(self.state, self.tool["outputs"], True, supportsMultipleInput, "outputSource")

        if wo is None:
            raise WorkflowException("Output for workflow not available")

        _logger.info(u"[%s] outdir is %s", self.name, self.outdir)

        output_callback(wo, self.processStatus)


class Workflow(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[unicode, Any], **Any) -> None
        super(Workflow, self).__init__(toolpath_object, **kwargs)

        kwargs["requirements"] = self.requirements
        kwargs["hints"] = self.hints

        makeTool = kwargs.get("makeTool")
        self.steps = [WorkflowStep(step, n, **kwargs) for n,step in enumerate(self.tool.get("steps", []))]
        random.shuffle(self.steps)

        # TODO: statically validate data links instead of doing it at runtime.

    def job(self, joborder, output_callback, **kwargs):
        # type: (Dict[unicode, unicode], Callable[[Any, Any], Any], **Any) -> Generator[WorkflowJob, None, None]
        builder = self._init_job(joborder, **kwargs)
        wj = WorkflowJob(self, **kwargs)
        yield wj

        kwargs["part_of"] = u"workflow %s" % wj.name

        for w in wj.job(builder.job, output_callback, **kwargs):
            yield w

    def visit(self, op):
        op(self.tool)
        for s in self.steps:
            s.visit(op)


class WorkflowStep(Process):

    def __init__(self, toolpath_object, pos, **kwargs):
        # type: (Dict[unicode, Any], int, **Any) -> None
        if "id" in toolpath_object:
            self.id = toolpath_object["id"]
        else:
            self.id = "#step" + str(pos)

        try:
            if isinstance(toolpath_object["run"], dict):
                self.embedded_tool = kwargs.get("makeTool")(toolpath_object["run"], **kwargs)
            else:
                self.embedded_tool = load_tool(
                    toolpath_object["run"], kwargs.get("makeTool"), kwargs,
                    enable_dev=kwargs.get("enable_dev"),
                    strict=kwargs.get("strict"))
        except validate.ValidationException as v:
            raise WorkflowException(u"Tool definition %s failed validation:\n%s" % (toolpath_object["run"], validate.indent(str(v))))

        for stepfield, toolfield in (("in", "inputs"), ("out", "outputs")):
            toolpath_object[toolfield] = []
            for step_entry in toolpath_object[stepfield]:
                if isinstance(step_entry, (str, unicode)):
                    param = {}  # type: Dict[str, Any]
                    inputid = step_entry
                else:
                    param = step_entry.copy()
                    inputid = step_entry["id"]

                shortinputid = shortname(inputid)
                found = False
                for tool_entry in self.embedded_tool.tool[toolfield]:
                    frag = shortname(tool_entry["id"])
                    if frag == shortinputid:
                        param.update(tool_entry)
                        found = True
                        break
                if not found:
                    param["type"] = "Any"
                param["id"] = inputid
                toolpath_object[toolfield].append(param)

        super(WorkflowStep, self).__init__(toolpath_object, **kwargs)

        if self.embedded_tool.tool["class"] == "Workflow":
            (feature, _) = self.get_requirement("SubworkflowFeatureRequirement")
            if not feature:
                raise WorkflowException("Workflow contains embedded workflow but SubworkflowFeatureRequirement not in requirements")

        if "scatter" in self.tool:
            (feature, _) = self.get_requirement("ScatterFeatureRequirement")
            if not feature:
                raise WorkflowException("Workflow contains scatter but ScatterFeatureRequirement not in requirements")

            inputparms = copy.deepcopy(self.tool["inputs"])
            outputparms = copy.deepcopy(self.tool["outputs"])
            scatter = aslist(self.tool["scatter"])

            method = self.tool.get("scatterMethod")
            if method is None and len(scatter) != 1:
                raise WorkflowException("Must specify scatterMethod when scattering over multiple inputs")

            inp_map = {i["id"]: i for i in inputparms}
            for s in scatter:
                if s not in inp_map:
                    raise WorkflowException(u"Scatter parameter '%s' does not correspond to an input parameter of this step, inputs are %s" % (s, inp_map.keys()))

                inp_map[s]["type"] = {"type": "array", "items": inp_map[s]["type"]}

            if self.tool.get("scatterMethod") == "nested_crossproduct":
                nesting = len(scatter)
            else:
                nesting = 1

            for r in xrange(0, nesting):
                for i in outputparms:
                    i["type"] = {"type": "array", "items": i["type"]}
            self.tool["inputs"] = inputparms
            self.tool["outputs"] = outputparms

    def receive_output(self, output_callback, jobout, processStatus):
        # type: (Callable[...,Any], Dict[unicode, str], str) -> None
        #_logger.debug("WorkflowStep output from run is %s", jobout)
        output = {}
        for i in self.tool["outputs"]:
            field = shortname(i["id"])
            if field in jobout:
                output[i["id"]] = jobout[field]
            else:
                processStatus = "permanentFail"
        output_callback(output, processStatus)

    def job(self, joborder, output_callback, **kwargs):
        # type: (Dict[unicode, Any], Callable[...,Any], **Any) -> Generator
        for i in self.tool["inputs"]:
            p = i["id"]
            field = shortname(p)
            joborder[field] = joborder[i["id"]]
            del joborder[i["id"]]

        kwargs["requirements"] = kwargs.get("requirements", []) + self.tool.get("requirements", [])
        kwargs["hints"] = kwargs.get("hints", []) + self.tool.get("hints", [])

        try:
            for t in self.embedded_tool.job(joborder,
                                            functools.partial(self.receive_output, output_callback),
                                            **kwargs):
                yield t
        except WorkflowException:
            _logger.error(u"Exception on step '%s'", kwargs.get("name"))
            raise
        except Exception as e:
            _logger.exception("Unexpected exception")
            raise WorkflowException(str(e))

    def visit(self, op):
        self.embedded_tool.visit(op)


class ReceiveScatterOutput(object):

    def __init__(self, output_callback, dest):
        # type: (Callable[..., Any], Dict[str,List[str]]) -> None
        self.dest = dest
        self.completed = 0
        self.processStatus = "success"
        self.total = None  # type: int
        self.output_callback = output_callback

    def receive_scatter_output(self, index, jobout, processStatus):
        # type: (int, Dict[str, str], str) -> None
        for k,v in jobout.items():
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


def dotproduct_scatter(process, joborder, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[unicode, Any], List[str], Callable[..., Any], **Any) -> Generator[WorkflowJob, None, None]
    l = None
    for s in scatter_keys:
        if l is None:
            l = len(joborder[s])
        elif l != len(joborder[s]):
            raise WorkflowException("Length of input arrays must be equal when performing dotproduct scatter.")

    output = {}  # type: Dict[str,List[str]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output)

    for n in range(0, l):
        jo = copy.copy(joborder)
        for s in scatter_keys:
            jo[s] = joborder[s][n]

        jo = kwargs["postScatterEval"](jo)

        for j in process.job(jo, functools.partial(rc.receive_scatter_output, n), **kwargs):
            yield j

    rc.setTotal(l)


def nested_crossproduct_scatter(process, joborder, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[unicode, Any], List[str], Callable[..., Any], **Any) -> Generator[WorkflowJob, None, None]
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    output = {}  # type: Dict[str,List[str]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output)

    for n in range(0, l):
        jo = copy.copy(joborder)
        jo[scatter_key] = joborder[scatter_key][n]

        if len(scatter_keys) == 1:
            jo = kwargs["postScatterEval"](jo)
            for j in process.job(jo, functools.partial(rc.receive_scatter_output, n), **kwargs):
                yield j
        else:
            for j in nested_crossproduct_scatter(process, jo,
                    scatter_keys[1:], cast(  # known bug with mypy
                        # https://github.com/python/mypy/issues/797
                        Callable[[Any], Any],
                        functools.partial(rc.receive_scatter_output, n)),
                    **kwargs):
                yield j

    rc.setTotal(l)


def crossproduct_size(joborder, scatter_keys):
    # type: (Dict[unicode, Any], List[str]) -> int
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
    # type: (WorkflowJobStep, Dict[unicode, Any], List[str], Union[ReceiveScatterOutput,Callable[..., Any]], int, **Any) -> Generator[WorkflowJob, None, None]
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    rc = None  # type: ReceiveScatterOutput

    if startindex == 0 and not isinstance(output_callback, ReceiveScatterOutput):
        output = {}  # type: Dict[str,List[str]]
        for i in process.tool["outputs"]:
            output[i["id"]] = [None] * crossproduct_size(joborder, scatter_keys)
        rc = ReceiveScatterOutput(output_callback, output)
    elif isinstance(output_callback, ReceiveScatterOutput):
        rc = output_callback
    else:
        raise Exception("Unhandled code path. Please report this.")

    put = startindex
    for n in range(0, l):
        jo = copy.copy(joborder)
        jo[scatter_key] = joborder[scatter_key][n]

        if len(scatter_keys) == 1:
            jo = kwargs["postScatterEval"](jo)
            for j in process.job(jo, functools.partial(rc.receive_scatter_output, put), **kwargs):
                yield j
            put += 1
        else:
            for j in flat_crossproduct_scatter(process, jo, scatter_keys[1:], rc, put, **kwargs):
                if j:
                    put += 1
                yield j

    rc.setTotal(put)
