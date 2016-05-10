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
    # type: (Union[List[str],str], WorkflowStateItem, str, Dict[str, Any], str, str) -> bool
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
    elif valueFrom is not None or are_same_type(src.parameter["type"], sinktype) or sinktype == "Any":
        # simply assign the value from state to input
        inputobj[iid] = copy.deepcopy(src.value)
        return True
    return False

def are_same_type(src, sink):  # type: (Any, Any) -> bool
    """Check for identical type specifications, ignoring extra keys like inputBinding.
    """
    if isinstance(src, dict) and isinstance(sink, dict):
        if src["type"] == "array" and sink["type"] == "array":
            if 'null' in sink["items"]:
                return are_same_type([src["items"]], [it for it in sink["items"] if it != 'null'])
            return are_same_type(src["items"], sink["items"])
        elif src["type"] == sink["type"]:
            return True
        else:
            return False
    else:
        return src == sink


def object_from_state(state, parms, frag_only, supportsMultipleInput):
    # type: (Dict[str,WorkflowStateItem], List[Dict[str, Any]], bool, bool) -> Dict[str, str]
    inputobj = {}  # type: Dict[str, str]
    for inp in parms:
        iid = inp["id"]
        if frag_only:
            iid = shortname(iid)
        if "source" in inp:
            if isinstance(inp["source"], list) and not supportsMultipleInput:
                raise WorkflowException("Workflow contains multiple inbound links to a single parameter but MultipleInputFeatureRequirement is not declared.")
            connections = aslist(inp["source"])
            for src in connections:
                if src in state and state[src] is not None:
                    if not match_types(inp["type"], state[src], iid, inputobj,
                                            inp.get("linkMerge", ("merge_nested" if len(connections) > 1 else None)),
                                       valueFrom=inp.get("valueFrom")):
                        raise WorkflowException(u"Type mismatch between source '%s' (%s) and sink '%s' (%s)" % (src, state[src].parameter["type"], inp["id"], inp["type"]))
                elif src not in state:
                    raise WorkflowException(u"Connect source '%s' on parameter '%s' does not exist" % (src, inp["id"]))
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

    def job(self, joborder, basedir, output_callback, **kwargs):
        # type: (Dict[str,str], str, functools.partial[None], **Any) -> Generator
        kwargs["part_of"] = self.name
        kwargs["name"] = shortname(self.id)
        for j in self.step.job(joborder, basedir, output_callback, **kwargs):
            yield j


class WorkflowJob(object):

    def __init__(self, workflow, **kwargs):
        # type: (Workflow, **Any) -> None
        self.workflow = workflow
        self.tool = workflow.tool
        self.steps = [WorkflowJobStep(s) for s in workflow.steps]
        self.id = workflow.tool["id"]
        self.state = None  # type: Dict[str, WorkflowStateItem]
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

    def try_make_job(self, step, basedir, **kwargs):
        # type: (WorkflowJobStep, str, **Any) -> Generator
        inputparms = step.tool["inputs"]
        outputparms = step.tool["outputs"]

        supportsMultipleInput = bool(self.workflow.get_requirement("MultipleInputFeatureRequirement")[0])

        try:
            inputobj = object_from_state(self.state, inputparms, False, supportsMultipleInput)
            if inputobj is None:
                _logger.debug(u"[%s] job step %s not ready", self.name, step.id)
                return

            if step.submitted:
                return

            _logger.debug(u"[%s] starting %s", self.name, step.name)

            callback = functools.partial(self.receive_output, step, outputparms)

            valueFrom = {i["id"]: i["valueFrom"] for i in step.tool["inputs"] if "valueFrom" in i}

            if len(valueFrom) > 0 and not bool(self.workflow.get_requirement("StepInputExpressionRequirement")[0]):
                raise WorkflowException("Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements")

            vfinputs = {shortname(k): v for k,v in inputobj.iteritems()}
            def valueFromFunc(k, v):  # type: (Any, Any) -> Any
                if k in valueFrom:
                    return expression.do_eval(valueFrom[k], vfinputs, self.workflow.requirements,
                                       None, None, {}, context=v)
                else:
                    return v

            if "scatter" in step.tool:
                scatter = aslist(step.tool["scatter"])
                method = step.tool.get("scatterMethod")
                if method is None and len(scatter) != 1:
                    raise WorkflowException("Must specify scatterMethod when scattering over multiple inputs")
                kwargs["valueFrom"] = valueFromFunc

                inputobj = {k: valueFromFunc(k, v) if k not in scatter else v
                            for k,v in inputobj.items()}

                if method == "dotproduct" or method is None:
                    jobs = dotproduct_scatter(step, inputobj, basedir, scatter,
                                              cast(  # known bug with mypy
                                                  # https://github.com/python/mypy/issues/797
                                                  Callable[[Any], Any],callback), **kwargs)
                elif method == "nested_crossproduct":
                    jobs = nested_crossproduct_scatter(step, inputobj, basedir,
                            scatter, cast(Callable[[Any], Any], callback),
                            # known bug in mypy
                            # https://github.com/python/mypy/issues/797
                            **kwargs)
                elif method == "flat_crossproduct":
                    jobs = flat_crossproduct_scatter(step, inputobj, basedir,
                                                     scatter,
                                                     cast(Callable[[Any], Any],
                                                         # known bug in mypy
                                                         # https://github.com/python/mypy/issues/797
                                                         callback), 0, **kwargs)
            else:
                _logger.debug(u"[job %s] job input %s", step.name, json.dumps(inputobj, indent=4))
                inputobj = {k: valueFromFunc(k, v) for k,v in inputobj.items()}
                _logger.debug(u"[job %s] evaluated job input to %s", step.name, json.dumps(inputobj, indent=4))
                jobs = step.job(inputobj, basedir, callback, **kwargs)

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

    def job(self, joborder, basedir, output_callback, move_outputs=True, **kwargs):
        # type: (Dict[str,str], str, Callable[[Any, Any], Any], bool, **Any) -> Generator[WorkflowJob, None, None]
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

        output_dirs = set()

        completed = 0
        while completed < len(self.steps) and self.processStatus == "success":
            made_progress = False

            for step in self.steps:
                if not step.submitted:
                    step.iterable = self.try_make_job(step, basedir, **kwargs)

                if step.iterable:
                    for newjob in step.iterable:
                        if newjob:
                            made_progress = True
                            if newjob.outdir:
                                output_dirs.add(newjob.outdir)
                            yield newjob
                        else:
                            break

            completed = sum(1 for s in self.steps if s.completed)

            if not made_progress and completed < len(self.steps):
                yield None

        supportsMultipleInput = bool(self.workflow.get_requirement("MultipleInputFeatureRequirement")[0])

        wo = object_from_state(self.state, self.tool["outputs"], True, supportsMultipleInput)

        if wo is None:
            raise WorkflowException("Output for workflow not available")

        if move_outputs:
            targets = set()  # type: Set[str]
            conflicts = set()

            outfiles = findfiles(wo)

            for f in outfiles:
                for a in output_dirs:
                    if f["path"].startswith(a):
                        src = f["path"]
                        dst = os.path.join(self.outdir, src[len(a)+1:])
                        if dst in targets:
                            conflicts.add(dst)
                        else:
                            targets.add(dst)

            for f in outfiles:
                for a in output_dirs:
                    if f["path"].startswith(a):
                        src = f["path"]
                        dst = os.path.join(self.outdir, src[len(a)+1:])
                        if dst in conflicts:
                            sp = os.path.splitext(dst)
                            dst = u"%s-%s%s" % (sp[0], str(random.randint(1, 1000000000)), sp[1])
                        dirname = os.path.dirname(dst)
                        if not os.path.exists(dirname):
                            os.makedirs(dirname)
                        _logger.debug(u"[%s] Moving '%s' to '%s'", self.name, src, dst)
                        shutil.move(src, dst)
                        f["path"] = dst

            for a in output_dirs:
                if os.path.exists(a) and empty_subtree(a):
                    if kwargs.get("rm_tmpdir", True):
                        _logger.debug(u"[%s] Removing intermediate output directory %s", self.name, a)
                        shutil.rmtree(a, True)

        _logger.info(u"[%s] outdir is %s", self.name, self.outdir)

        output_callback(wo, self.processStatus)


class Workflow(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[str, Any], **Any) -> None
        super(Workflow, self).__init__(toolpath_object, **kwargs)

        kwargs["requirements"] = self.requirements
        kwargs["hints"] = self.hints

        makeTool = kwargs.get("makeTool")
        self.steps = [WorkflowStep(step, n, **kwargs) for n,step in enumerate(self.tool.get("steps", []))]
        random.shuffle(self.steps)

        # TODO: statically validate data links instead of doing it at runtime.

    def job(self, joborder, basedir, output_callback, **kwargs):
        # type: (Dict[str,str], str, Callable[[Any, Any], Any], **Any) -> Generator[WorkflowJob, None, None]
        builder = self._init_job(joborder, basedir, **kwargs)
        wj = WorkflowJob(self, **kwargs)
        yield wj

        kwargs["part_of"] = u"workflow %s" % wj.name

        for w in wj.job(builder.job, basedir, output_callback, **kwargs):
            yield w

    def visit(self, op):
        op(self.tool)
        for s in self.steps:
            s.visit(op)


class WorkflowStep(Process):

    def __init__(self, toolpath_object, pos, **kwargs):
        # type: (Dict[str, Any], int, **Any) -> None
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
        # type: (Callable[...,Any], Dict[str, str], str) -> None
        #_logger.debug("WorkflowStep output from run is %s", jobout)
        output = {}
        for i in self.tool["outputs"]:
            field = shortname(i["id"])
            if field in jobout:
                output[i["id"]] = jobout[field]
            else:
                processStatus = "permanentFail"
        output_callback(output, processStatus)

    def job(self, joborder, basedir, output_callback, **kwargs):
        # type: (Dict[str, Any], str, Callable[...,Any], **Any) -> Generator
        for i in self.tool["inputs"]:
            p = i["id"]
            field = shortname(p)
            joborder[field] = joborder[i["id"]]
            del joborder[i["id"]]

        kwargs["requirements"] = kwargs.get("requirements", []) + self.tool.get("requirements", [])
        kwargs["hints"] = kwargs.get("hints", []) + self.tool.get("hints", [])

        try:
            for t in self.embedded_tool.job(joborder, basedir,
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


def dotproduct_scatter(process, joborder, basedir, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[str, Any], str, List[str], Callable[..., Any], **Any) -> Generator[WorkflowJob, None, None]
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
            jo[s] = kwargs["valueFrom"](s, joborder[s][n])

        for j in process.job(jo, basedir, functools.partial(rc.receive_scatter_output, n), **kwargs):
            yield j

    rc.setTotal(l)


def nested_crossproduct_scatter(process, joborder, basedir, scatter_keys, output_callback, **kwargs):
    # type: (WorkflowJobStep, Dict[str, Any], str, List[str], Callable[..., Any], **Any) -> Generator[WorkflowJob, None, None]
    scatter_key = scatter_keys[0]
    l = len(joborder[scatter_key])
    output = {}  # type: Dict[str,List[str]]
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * l

    rc = ReceiveScatterOutput(output_callback, output)

    for n in range(0, l):
        jo = copy.copy(joborder)
        jo[scatter_key] = kwargs["valueFrom"](scatter_key, joborder[scatter_key][n])

        if len(scatter_keys) == 1:
            for j in process.job(jo, basedir, functools.partial(rc.receive_scatter_output, n), **kwargs):
                yield j
        else:
            for j in nested_crossproduct_scatter(process, jo, basedir,
                    scatter_keys[1:], cast(  # known bug with mypy
                        # https://github.com/python/mypy/issues/797
                        Callable[[Any], Any],
                        functools.partial(rc.receive_scatter_output, n)),
                    **kwargs):
                yield j

    rc.setTotal(l)


def crossproduct_size(joborder, scatter_keys):
    # type: (Dict[str, Any], List[str]) -> int
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

def flat_crossproduct_scatter(process, joborder, basedir, scatter_keys, output_callback, startindex, **kwargs):
    # type: (WorkflowJobStep, Dict[str, Any], str, List[str], Union[ReceiveScatterOutput,Callable[..., Any]], int, **Any) -> Generator[WorkflowJob, None, None]
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
        jo[scatter_key] = kwargs["valueFrom"](scatter_key, joborder[scatter_key][n])

        if len(scatter_keys) == 1:
            for j in process.job(jo, basedir, functools.partial(rc.receive_scatter_output, put), **kwargs):
                yield j
            put += 1
        else:
            for j in flat_crossproduct_scatter(process, jo, basedir, scatter_keys[1:], rc, put, **kwargs):
                if j:
                    put += 1
                yield j

    rc.setTotal(put)
