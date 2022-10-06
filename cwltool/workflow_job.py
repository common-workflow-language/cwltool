import copy
import datetime
import functools
import logging
import threading
from typing import (
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Sized,
    Tuple,
    Union,
    cast,
)

from cwl_utils import expression
from schema_salad.sourceline import SourceLine
from schema_salad.utils import json_dumps
from typing_extensions import TYPE_CHECKING

from .builder import content_limit_respected_read
from .checker import can_assign_src_to_sink
from .context import RuntimeContext, getdefault
from .errors import WorkflowException
from .loghandler import _logger
from .process import shortname, uniquename
from .stdfsaccess import StdFsAccess
from .utils import (
    CWLObjectType,
    CWLOutputType,
    JobsGeneratorType,
    OutputCallbackType,
    ParametersType,
    ScatterDestinationsType,
    ScatterOutputCallbackType,
    SinkType,
    WorkflowStateItem,
    adjustDirObjs,
    aslist,
    get_listing,
)

if TYPE_CHECKING:
    from .provenance_profile import ProvenanceProfile
    from .workflow import Workflow, WorkflowStep


class WorkflowJobStep:
    """Generated for each step in Workflow.steps()."""

    def __init__(self, step: "WorkflowStep") -> None:
        """Initialize this WorkflowJobStep."""
        self.step = step
        self.tool = step.tool
        self.id = step.id
        self.submitted = False
        self.iterable = None  # type: Optional[JobsGeneratorType]
        self.completed = False
        self.name = uniquename("step %s" % shortname(self.id))
        self.prov_obj = step.prov_obj
        self.parent_wf = step.parent_wf

    def job(
        self,
        joborder: CWLObjectType,
        output_callback: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        runtimeContext = runtimeContext.copy()
        runtimeContext.part_of = self.name
        runtimeContext.name = shortname(self.id)

        _logger.info("[%s] start", self.name)

        yield from self.step.job(joborder, output_callback, runtimeContext)


class ReceiveScatterOutput:
    """Produced by the scatter generators."""

    def __init__(
        self,
        output_callback: ScatterOutputCallbackType,
        dest: ScatterDestinationsType,
        total: int,
    ) -> None:
        """Initialize."""
        self.dest = dest
        self.completed = 0
        self.processStatus = "success"
        self.total = total
        self.output_callback = output_callback
        self.steps = []  # type: List[Optional[JobsGeneratorType]]

    def receive_scatter_output(
        self, index: int, jobout: CWLObjectType, processStatus: str
    ) -> None:
        for key, val in jobout.items():
            self.dest[key][index] = val

        # Release the iterable related to this step to
        # reclaim memory.
        if self.steps:
            self.steps[index] = None

        if processStatus != "success":
            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

        self.completed += 1

        if self.completed == self.total:
            self.output_callback(self.dest, self.processStatus)

    def setTotal(
        self,
        total: int,
        steps: List[Optional[JobsGeneratorType]],
    ) -> None:
        """
        Set the total number of expected outputs along with the steps.

        This is necessary to finish the setup.
        """
        self.total = total
        self.steps = steps
        if self.completed == self.total:
            self.output_callback(self.dest, self.processStatus)


def parallel_steps(
    steps: List[Optional[JobsGeneratorType]],
    rc: ReceiveScatterOutput,
    runtimeContext: RuntimeContext,
) -> JobsGeneratorType:
    while rc.completed < rc.total:
        made_progress = False
        for index, step in enumerate(steps):
            if getdefault(
                runtimeContext.on_error, "stop"
            ) == "stop" and rc.processStatus not in ("success", "skipped"):
                break
            if step is None:
                continue
            try:
                for j in step:
                    if getdefault(
                        runtimeContext.on_error, "stop"
                    ) == "stop" and rc.processStatus not in ("success", "skipped"):
                        break
                    if j is not None:
                        made_progress = True
                        yield j
                    else:
                        break
                if made_progress:
                    break
            except WorkflowException as exc:
                _logger.error("Cannot make scatter job: %s", str(exc))
                _logger.debug("", exc_info=True)
                rc.receive_scatter_output(index, {}, "permanentFail")
        if not made_progress and rc.completed < rc.total:
            yield None


def nested_crossproduct_scatter(
    process: WorkflowJobStep,
    joborder: CWLObjectType,
    scatter_keys: MutableSequence[str],
    output_callback: ScatterOutputCallbackType,
    runtimeContext: RuntimeContext,
) -> JobsGeneratorType:
    scatter_key = scatter_keys[0]
    jobl = len(cast(Sized, joborder[scatter_key]))
    output = {}  # type: ScatterDestinationsType
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * jobl

    rc = ReceiveScatterOutput(output_callback, output, jobl)

    steps = []  # type: List[Optional[JobsGeneratorType]]
    for index in range(0, jobl):
        sjob = copy.copy(joborder)  # type: Optional[CWLObjectType]
        assert sjob is not None  # nosec
        sjob[scatter_key] = cast(
            MutableMapping[int, CWLObjectType], joborder[scatter_key]
        )[index]

        if len(scatter_keys) == 1:
            if runtimeContext.postScatterEval is not None:
                sjob = runtimeContext.postScatterEval(sjob)
            curriedcallback = functools.partial(rc.receive_scatter_output, index)
            if sjob is not None:
                steps.append(process.job(sjob, curriedcallback, runtimeContext))
            else:
                curriedcallback({}, "skipped")
                steps.append(None)
        else:
            steps.append(
                nested_crossproduct_scatter(
                    process,
                    sjob,
                    scatter_keys[1:],
                    functools.partial(rc.receive_scatter_output, index),
                    runtimeContext,
                )
            )

    rc.setTotal(jobl, steps)
    return parallel_steps(steps, rc, runtimeContext)


def crossproduct_size(
    joborder: CWLObjectType, scatter_keys: MutableSequence[str]
) -> int:
    scatter_key = scatter_keys[0]
    if len(scatter_keys) == 1:
        ssum = len(cast(Sized, joborder[scatter_key]))
    else:
        ssum = 0
        for _ in range(0, len(cast(Sized, joborder[scatter_key]))):
            ssum += crossproduct_size(joborder, scatter_keys[1:])
    return ssum


def flat_crossproduct_scatter(
    process: WorkflowJobStep,
    joborder: CWLObjectType,
    scatter_keys: MutableSequence[str],
    output_callback: ScatterOutputCallbackType,
    runtimeContext: RuntimeContext,
) -> JobsGeneratorType:
    output = {}  # type: ScatterDestinationsType
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * crossproduct_size(joborder, scatter_keys)
    callback = ReceiveScatterOutput(output_callback, output, 0)
    (steps, total) = _flat_crossproduct_scatter(
        process, joborder, scatter_keys, callback, 0, runtimeContext
    )
    callback.setTotal(total, steps)
    return parallel_steps(steps, callback, runtimeContext)


def _flat_crossproduct_scatter(
    process: WorkflowJobStep,
    joborder: CWLObjectType,
    scatter_keys: MutableSequence[str],
    callback: ReceiveScatterOutput,
    startindex: int,
    runtimeContext: RuntimeContext,
) -> Tuple[List[Optional[JobsGeneratorType]], int,]:
    """Inner loop."""
    scatter_key = scatter_keys[0]
    jobl = len(cast(Sized, joborder[scatter_key]))
    steps = []  # type: List[Optional[JobsGeneratorType]]
    put = startindex
    for index in range(0, jobl):
        sjob = copy.copy(joborder)  # type: Optional[CWLObjectType]
        assert sjob is not None  # nosec
        sjob[scatter_key] = cast(
            MutableMapping[int, CWLObjectType], joborder[scatter_key]
        )[index]

        if len(scatter_keys) == 1:
            if runtimeContext.postScatterEval is not None:
                sjob = runtimeContext.postScatterEval(sjob)
            curriedcallback = functools.partial(callback.receive_scatter_output, put)
            if sjob is not None:
                steps.append(process.job(sjob, curriedcallback, runtimeContext))
            else:
                curriedcallback({}, "skipped")
                steps.append(None)
            put += 1
        else:
            (add, _) = _flat_crossproduct_scatter(
                process, sjob, scatter_keys[1:], callback, put, runtimeContext
            )
            put += len(add)
            steps.extend(add)

    return (steps, put)


def dotproduct_scatter(
    process: WorkflowJobStep,
    joborder: CWLObjectType,
    scatter_keys: MutableSequence[str],
    output_callback: ScatterOutputCallbackType,
    runtimeContext: RuntimeContext,
) -> JobsGeneratorType:
    jobl = None  # type: Optional[int]
    for key in scatter_keys:
        if jobl is None:
            jobl = len(cast(Sized, joborder[key]))
        elif jobl != len(cast(Sized, joborder[key])):
            raise WorkflowException(
                "Length of input arrays must be equal when performing "
                "dotproduct scatter."
            )
    if jobl is None:
        raise Exception("Impossible codepath")

    output = {}  # type: ScatterDestinationsType
    for i in process.tool["outputs"]:
        output[i["id"]] = [None] * jobl

    rc = ReceiveScatterOutput(output_callback, output, jobl)

    steps = []  # type: List[Optional[JobsGeneratorType]]
    for index in range(0, jobl):
        sjobo = copy.copy(joborder)  # type: Optional[CWLObjectType]
        assert sjobo is not None  # nosec
        for key in scatter_keys:
            sjobo[key] = cast(MutableMapping[int, CWLObjectType], joborder[key])[index]

        if runtimeContext.postScatterEval is not None:
            sjobo = runtimeContext.postScatterEval(sjobo)
        curriedcallback = functools.partial(rc.receive_scatter_output, index)
        if sjobo is not None:
            steps.append(process.job(sjobo, curriedcallback, runtimeContext))
        else:
            curriedcallback({}, "skipped")
            steps.append(None)

    rc.setTotal(jobl, steps)
    return parallel_steps(steps, rc, runtimeContext)


def match_types(
    sinktype: Optional[SinkType],
    src: WorkflowStateItem,
    iid: str,
    inputobj: CWLObjectType,
    linkMerge: Optional[str],
    valueFrom: Optional[str],
) -> bool:
    if isinstance(sinktype, MutableSequence):
        # Sink is union type
        for st in sinktype:
            if match_types(st, src, iid, inputobj, linkMerge, valueFrom):
                return True
    elif isinstance(src.parameter["type"], MutableSequence):
        # Source is union type
        # Check that at least one source type is compatible with the sink.
        original_types = src.parameter["type"]
        for source_type in original_types:
            src.parameter["type"] = source_type
            match = match_types(sinktype, src, iid, inputobj, linkMerge, valueFrom)
            if match:
                src.parameter["type"] = original_types
                return True
        src.parameter["type"] = original_types
        return False
    elif linkMerge:
        if iid not in inputobj:
            inputobj[iid] = []
        sourceTypes = cast(List[Optional[CWLOutputType]], inputobj[iid])
        if linkMerge == "merge_nested":
            sourceTypes.append(src.value)
        elif linkMerge == "merge_flattened":
            if isinstance(src.value, MutableSequence):
                sourceTypes.extend(src.value)
            else:
                sourceTypes.append(src.value)
        else:
            raise WorkflowException("Unrecognized linkMerge enum '%s'" % linkMerge)
        return True
    elif (
        valueFrom is not None
        or can_assign_src_to_sink(cast(SinkType, src.parameter["type"]), sinktype)
        or sinktype == "Any"
    ):
        # simply assign the value from state to input
        inputobj[iid] = copy.deepcopy(src.value)
        return True
    return False


def object_from_state(
    state: Dict[str, Optional[WorkflowStateItem]],
    params: ParametersType,
    frag_only: bool,
    supportsMultipleInput: bool,
    sourceField: str,
    incomplete: bool = False,
) -> Optional[CWLObjectType]:
    inputobj = {}  # type: CWLObjectType
    for inp in params:
        iid = original_id = cast(str, inp["id"])
        if frag_only:
            iid = shortname(iid)
        if sourceField in inp:
            connections = aslist(inp[sourceField])
            if len(connections) > 1 and not supportsMultipleInput:
                raise WorkflowException(
                    "Workflow contains multiple inbound links to a single "
                    "parameter but MultipleInputFeatureRequirement is not "
                    "declared."
                )
            for src in connections:
                a_state = state.get(src, None)
                if a_state is not None and (
                    a_state.success in ("success", "skipped") or incomplete
                ):
                    if not match_types(
                        inp["type"],
                        a_state,
                        iid,
                        inputobj,
                        cast(
                            Optional[str],
                            inp.get(
                                "linkMerge",
                                ("merge_nested" if len(connections) > 1 else None),
                            ),
                        ),
                        valueFrom=cast(str, inp.get("valueFrom")),
                    ):
                        raise WorkflowException(
                            "Type mismatch between source '%s' (%s) and "
                            "sink '%s' (%s)"
                            % (src, a_state.parameter["type"], original_id, inp["type"])
                        )
                elif src not in state:
                    raise WorkflowException(
                        "Connect source '%s' on parameter '%s' does not "
                        "exist" % (src, original_id)
                    )
                elif not incomplete:
                    return None

        if "pickValue" in inp and isinstance(inputobj.get(iid), MutableSequence):
            seq = cast(MutableSequence[Optional[CWLOutputType]], inputobj.get(iid))
            if inp["pickValue"] == "first_non_null":
                found = False
                for v in seq:
                    if v is not None:
                        found = True
                        inputobj[iid] = v
                        break
                if not found:
                    raise WorkflowException(
                        "All sources for '%s' are null" % (shortname(original_id))
                    )
            elif inp["pickValue"] == "the_only_non_null":
                found = False
                for v in seq:
                    if v is not None:
                        if found:
                            raise WorkflowException(
                                "Expected only one source for '%s' to be non-null, got %s"
                                % (shortname(original_id), seq)
                            )
                        found = True
                        inputobj[iid] = v
                if not found:
                    raise WorkflowException(
                        "All sources for '%s' are null" % (shortname(original_id))
                    )
            elif inp["pickValue"] == "all_non_null":
                inputobj[iid] = [v for v in seq if v is not None]

        if inputobj.get(iid) is None and "default" in inp:
            inputobj[iid] = inp["default"]

        if iid not in inputobj and ("valueFrom" in inp or incomplete):
            inputobj[iid] = None

        if iid not in inputobj:
            raise WorkflowException("Value for %s not specified" % original_id)
    return inputobj


class WorkflowJob:
    """Generates steps from the Workflow."""

    def __init__(self, workflow: "Workflow", runtimeContext: RuntimeContext) -> None:
        """Initialize this WorkflowJob."""
        self.workflow = workflow
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.parent_wf = None  # type: Optional[ProvenanceProfile]
        self.tool = workflow.tool
        if runtimeContext.research_obj is not None:
            self.prov_obj = workflow.provenance_object
            self.parent_wf = workflow.parent_wf
        self.steps = [WorkflowJobStep(s) for s in workflow.steps]
        self.state = {}  # type: Dict[str, Optional[WorkflowStateItem]]
        self.processStatus = ""
        self.did_callback = False
        self.made_progress = None  # type: Optional[bool]
        self.outdir = runtimeContext.get_outdir()

        self.name = uniquename(
            "workflow {}".format(
                getdefault(
                    runtimeContext.name,
                    shortname(self.workflow.tool.get("id", "embedded")),
                )
            )
        )

        _logger.debug(
            "[%s] initialized from %s",
            self.name,
            self.tool.get("id", "workflow embedded in %s" % runtimeContext.part_of),
        )

    def do_output_callback(self, final_output_callback: OutputCallbackType) -> None:

        supportsMultipleInput = bool(
            self.workflow.get_requirement("MultipleInputFeatureRequirement")[0]
        )

        wo = None  # type: Optional[CWLObjectType]
        try:
            wo = object_from_state(
                self.state,
                self.tool["outputs"],
                True,
                supportsMultipleInput,
                "outputSource",
                incomplete=True,
            )
        except WorkflowException as err:
            _logger.error(
                "[%s] Cannot collect workflow output: %s", self.name, str(err)
            )
            self.processStatus = "permanentFail"
        if (
            self.prov_obj
            and self.parent_wf
            and self.prov_obj.workflow_run_uri != self.parent_wf.workflow_run_uri
        ):
            process_run_id = None  # type: Optional[str]
            self.prov_obj.generate_output_prov(wo or {}, process_run_id, self.name)
            self.prov_obj.document.wasEndedBy(
                self.prov_obj.workflow_run_uri,
                None,
                self.prov_obj.engine_uuid,
                datetime.datetime.now(),
            )
            prov_ids = self.prov_obj.finalize_prov_profile(self.name)
            # Tell parent to associate our provenance files with our wf run
            self.parent_wf.activity_has_provenance(
                self.prov_obj.workflow_run_uri, prov_ids
            )

        _logger.info("[%s] completed %s", self.name, self.processStatus)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("[%s] outputs %s", self.name, json_dumps(wo, indent=4))

        self.did_callback = True

        final_output_callback(wo, self.processStatus)

    def receive_output(
        self,
        step: WorkflowJobStep,
        outputparms: List[CWLObjectType],
        final_output_callback: OutputCallbackType,
        jobout: CWLObjectType,
        processStatus: str,
    ) -> None:

        for i in outputparms:
            if "id" in i:
                iid = cast(str, i["id"])
                if iid in jobout:
                    self.state[iid] = WorkflowStateItem(i, jobout[iid], processStatus)
                else:
                    _logger.error(
                        "[%s] Output is missing expected field %s", step.name, iid
                    )
                    processStatus = "permanentFail"
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "[%s] produced output %s", step.name, json_dumps(jobout, indent=4)
            )

        if processStatus not in ("success", "skipped"):
            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

            _logger.warning("[%s] completed %s", step.name, processStatus)
        else:
            _logger.info("[%s] completed %s", step.name, processStatus)

        step.completed = True
        # Release the iterable related to this step to
        # reclaim memory.
        step.iterable = None
        self.made_progress = True

        completed = sum(1 for s in self.steps if s.completed)
        if completed == len(self.steps):
            self.do_output_callback(final_output_callback)

    def try_make_job(
        self,
        step: WorkflowJobStep,
        final_output_callback: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        container_engine = "docker"
        if runtimeContext.podman:
            container_engine = "podman"
        elif runtimeContext.singularity:
            container_engine = "singularity"
        if step.submitted:
            return

        inputparms = step.tool["inputs"]
        outputparms = step.tool["outputs"]

        supportsMultipleInput = bool(
            self.workflow.get_requirement("MultipleInputFeatureRequirement")[0]
        )

        try:
            inputobj = object_from_state(
                self.state, inputparms, False, supportsMultipleInput, "source"
            )
            if inputobj is None:
                _logger.debug("[%s] job step %s not ready", self.name, step.id)
                return

            _logger.info("[%s] starting %s", self.name, step.name)

            callback = functools.partial(
                self.receive_output, step, outputparms, final_output_callback
            )

            valueFrom = {
                i["id"]: i["valueFrom"] for i in step.tool["inputs"] if "valueFrom" in i
            }

            loadContents = {
                i["id"] for i in step.tool["inputs"] if i.get("loadContents")
            }

            if len(valueFrom) > 0 and not bool(
                self.workflow.get_requirement("StepInputExpressionRequirement")[0]
            ):
                raise WorkflowException(
                    "Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements"
                )

            def postScatterEval(io: CWLObjectType) -> Optional[CWLObjectType]:
                shortio = cast(CWLObjectType, {shortname(k): v for k, v in io.items()})

                fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)("")
                for k, v in io.items():
                    if k in loadContents:
                        val = cast(CWLObjectType, v)
                        if val.get("contents") is None:
                            with fs_access.open(cast(str, val["location"]), "rb") as f:
                                val["contents"] = content_limit_respected_read(f)

                def valueFromFunc(
                    k: str, v: Optional[CWLOutputType]
                ) -> Optional[CWLOutputType]:
                    if k in valueFrom:
                        adjustDirObjs(
                            v, functools.partial(get_listing, fs_access, recursive=True)
                        )

                        return expression.do_eval(
                            valueFrom[k],
                            shortio,
                            self.workflow.requirements,
                            None,
                            None,
                            {},
                            context=v,
                            debug=runtimeContext.debug,
                            js_console=runtimeContext.js_console,
                            timeout=runtimeContext.eval_timeout,
                            container_engine=container_engine,
                        )
                    return v

                psio = {k: valueFromFunc(k, v) for k, v in io.items()}
                if "when" in step.tool:
                    evalinputs = {shortname(k): v for k, v in psio.items()}
                    whenval = expression.do_eval(
                        step.tool["when"],
                        evalinputs,
                        self.workflow.requirements,
                        None,
                        None,
                        {},
                        debug=runtimeContext.debug,
                        js_console=runtimeContext.js_console,
                        timeout=runtimeContext.eval_timeout,
                        container_engine=container_engine,
                    )
                    if whenval is True:
                        pass
                    elif whenval is False:
                        _logger.debug(
                            "[%s] conditional %s evaluated to %s",
                            step.name,
                            step.tool["when"],
                            whenval,
                        )
                        _logger.debug(
                            "[%s] inputs was %s",
                            step.name,
                            json_dumps(evalinputs, indent=2),
                        )
                        return None
                    else:
                        raise WorkflowException(
                            "Conditional 'when' must evaluate to 'true' or 'false'"
                        )
                return psio

            if "scatter" in step.tool:
                scatter = cast(List[str], aslist(step.tool["scatter"]))
                method = step.tool.get("scatterMethod")
                if method is None and len(scatter) != 1:
                    raise WorkflowException(
                        "Must specify scatterMethod when scattering over multiple inputs"
                    )
                runtimeContext = runtimeContext.copy()
                runtimeContext.postScatterEval = postScatterEval

                emptyscatter = [
                    shortname(s) for s in scatter if len(cast(Sized, inputobj[s])) == 0
                ]
                if emptyscatter:
                    _logger.warning(
                        "[job %s] Notice: scattering over empty input in "
                        "'%s'.  All outputs will be empty.",
                        step.name,
                        "', '".join(emptyscatter),
                    )

                if method == "dotproduct" or method is None:
                    jobs = dotproduct_scatter(
                        step, inputobj, scatter, callback, runtimeContext
                    )
                elif method == "nested_crossproduct":
                    jobs = nested_crossproduct_scatter(
                        step, inputobj, scatter, callback, runtimeContext
                    )
                elif method == "flat_crossproduct":
                    jobs = flat_crossproduct_scatter(
                        step, inputobj, scatter, callback, runtimeContext
                    )
            else:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(
                        "[%s] job input %s", step.name, json_dumps(inputobj, indent=4)
                    )

                inputobj = postScatterEval(inputobj)
                if inputobj is not None:
                    if _logger.isEnabledFor(logging.DEBUG):
                        _logger.debug(
                            "[%s] evaluated job input to %s",
                            step.name,
                            json_dumps(inputobj, indent=4),
                        )
                    if step.step.get_requirement("http://commonwl.org/cwltool#Loop")[0]:
                        jobs = WorkflowJobLoopStep(
                            step=step, container_engine=container_engine
                        ).job(inputobj, callback, runtimeContext)
                    else:
                        jobs = step.job(inputobj, callback, runtimeContext)
                else:
                    _logger.info("[%s] will be skipped", step.name)
                    callback({k["id"]: None for k in outputparms}, "skipped")
                    step.completed = True
                    jobs = (_ for _ in ())

            step.submitted = True

            yield from jobs
        except WorkflowException:
            raise
        except Exception:
            _logger.exception("Unhandled exception")
            self.processStatus = "permanentFail"
            step.completed = True

    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:
        """Log the start of each workflow."""
        _logger.info("[%s] start", self.name)

    def job(
        self,
        joborder: CWLObjectType,
        output_callback: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        self.state = {}
        self.processStatus = "success"

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("[%s] inputs %s", self.name, json_dumps(joborder, indent=4))

        runtimeContext = runtimeContext.copy()
        runtimeContext.outdir = None
        debug = runtimeContext.debug

        for index, inp in enumerate(self.tool["inputs"]):
            with SourceLine(self.tool["inputs"], index, WorkflowException, debug):
                inp_id = shortname(inp["id"])
                if inp_id in joborder:
                    self.state[inp["id"]] = WorkflowStateItem(
                        inp, joborder[inp_id], "success"
                    )
                elif "default" in inp:
                    self.state[inp["id"]] = WorkflowStateItem(
                        inp, inp["default"], "success"
                    )
                else:
                    raise WorkflowException(
                        "Input '%s' not in input object and does not have a "
                        " default value." % (inp["id"])
                    )

        for step in self.steps:
            for out in step.tool["outputs"]:
                self.state[out["id"]] = None

        completed = 0
        while completed < len(self.steps):
            self.made_progress = False

            for step in self.steps:
                if (
                    getdefault(runtimeContext.on_error, "stop") == "stop"
                    and self.processStatus != "success"
                ):
                    break

                if not step.submitted:
                    try:
                        step.iterable = self.try_make_job(
                            step, output_callback, runtimeContext
                        )
                    except WorkflowException as exc:
                        _logger.error("[%s] Cannot make job: %s", step.name, str(exc))
                        _logger.debug("", exc_info=True)
                        self.processStatus = "permanentFail"

                if step.iterable is not None:
                    try:
                        for newjob in step.iterable:
                            if (
                                getdefault(runtimeContext.on_error, "stop") == "stop"
                                and self.processStatus != "success"
                            ):
                                break
                            if newjob is not None:
                                self.made_progress = True
                                yield newjob
                            else:
                                break
                    except WorkflowException as exc:
                        _logger.error("[%s] Cannot make job: %s", step.name, str(exc))
                        _logger.debug("", exc_info=True)
                        self.processStatus = "permanentFail"

            completed = sum(1 for s in self.steps if s.completed)

            if not self.made_progress and completed < len(self.steps):
                if self.processStatus != "success":
                    break
                else:
                    yield None

        if not self.did_callback and output_callback:
            # could have called earlier on line 336;
            self.do_output_callback(output_callback)
            # depends which one comes first. All steps are completed
            # or all outputs have been produced.


class WorkflowJobLoopStep:
    """Generated for each step in Workflow.steps() containing a http://commonwl.org/cwltool#Loop requirement."""

    def __init__(self, step: WorkflowJobStep, container_engine: str):
        """Initialize this WorkflowJobLoopStep."""
        self.step: WorkflowJobStep = step
        self.container_engine: str = container_engine
        self.joborder: Optional[CWLObjectType] = None
        self.processStatus: str = "success"
        self.iteration: int = 0
        self.output_buffer: MutableMapping[
            str,
            Union[MutableSequence[Optional[CWLOutputType]], Optional[CWLOutputType]],
        ] = {}

    def _set_empty_output(self, loop_req: CWLObjectType) -> None:
        for i in self.step.tool["outputs"]:
            if "id" in i:
                iid = cast(str, i["id"])
                if loop_req.get("outputMethod") == "all":
                    self.output_buffer[iid] = cast(
                        MutableSequence[Optional[CWLOutputType]], []
                    )
                else:
                    self.output_buffer[iid] = None

    def job(
        self,
        joborder: CWLObjectType,
        output_callback: OutputCallbackType,
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        """Generate a WorkflowJobStep job until the `loopWhen` condition evaluates to False."""
        self.joborder = joborder
        loop_req = cast(
            CWLObjectType,
            self.step.step.get_requirement("http://commonwl.org/cwltool#Loop")[0],
        )

        callback = functools.partial(
            self.loop_callback,
            runtimeContext,
        )

        try:
            while True:
                evalinputs = {shortname(k): v for k, v in self.joborder.items()}
                whenval = expression.do_eval(
                    loop_req["loopWhen"],
                    evalinputs,
                    self.step.step.requirements,
                    None,
                    None,
                    {},
                    debug=runtimeContext.debug,
                    js_console=runtimeContext.js_console,
                    timeout=runtimeContext.eval_timeout,
                    container_engine=self.container_engine,
                )
                if whenval is True:
                    self.processStatus = ""
                    yield from self.step.job(self.joborder, callback, runtimeContext)
                    while self.processStatus == "":
                        yield None
                    if self.processStatus == "permanentFail":
                        output_callback(self.output_buffer, self.processStatus)
                        return
                elif whenval is False:
                    _logger.debug(
                        "[%s] loop condition %s evaluated to %s at iteration %i",
                        self.step.name,
                        loop_req["loopWhen"],
                        whenval,
                        self.iteration,
                    )
                    _logger.debug(
                        "[%s] inputs was %s",
                        self.step.name,
                        json_dumps(evalinputs, indent=2),
                    )
                    if self.iteration == 0:
                        self.processStatus = "skipped"
                        self._set_empty_output(loop_req)
                    output_callback(self.output_buffer, self.processStatus)
                    return
                else:
                    raise WorkflowException(
                        "Loop condition 'loopWhen' must evaluate to 'true' or 'false'"
                    )
        except WorkflowException:
            raise
        except Exception:
            _logger.exception("Unhandled exception")
            self.processStatus = "permanentFail"
            if self.iteration == 0:
                self._set_empty_output(loop_req)
            output_callback(self.output_buffer, self.processStatus)

    def loop_callback(
        self,
        runtimeContext: RuntimeContext,
        jobout: CWLObjectType,
        processStatus: str,
    ) -> None:
        """Update the joborder object with output values from the last iteration."""
        self.iteration += 1
        try:
            loop_req = cast(
                CWLObjectType,
                self.step.step.get_requirement("http://commonwl.org/cwltool#Loop")[0],
            )
            state: Dict[str, Optional[WorkflowStateItem]] = {}
            for i in self.step.tool["outputs"]:
                if "id" in i:
                    iid = cast(str, i["id"])
                    if iid in jobout:
                        state[iid] = WorkflowStateItem(i, jobout[iid], processStatus)
                        if loop_req.get("outputMethod") == "all":
                            if iid not in self.output_buffer:
                                self.output_buffer[iid] = cast(
                                    MutableSequence[Optional[CWLOutputType]], []
                                )
                            cast(
                                MutableSequence[Optional[CWLOutputType]],
                                self.output_buffer[iid],
                            ).append(jobout[iid])
                        else:
                            self.output_buffer[iid] = jobout[iid]
                    else:
                        _logger.error(
                            "[%s] Output of iteration %i is missing expected field %s",
                            self.step.name,
                            self.iteration,
                            iid,
                        )
                        processStatus = "permanentFail"
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    "Iteration %i of [%s] produced output %s",
                    self.iteration,
                    self.step.name,
                    json_dumps(jobout, indent=4),
                )

            if self.processStatus != "permanentFail":
                self.processStatus = processStatus

            if processStatus not in ("success", "skipped"):

                _logger.warning(
                    "[%s] Iteration %i completed %s",
                    self.step.name,
                    self.iteration,
                    processStatus,
                )
            else:
                _logger.info(
                    "[%s] Iteration %i completed %s",
                    self.step.name,
                    self.iteration,
                    processStatus,
                )

            supportsMultipleInput = bool(
                self.step.step.get_requirement("MultipleInputFeatureRequirement")[0]
            )

            inputobj = {
                **cast(CWLObjectType, self.joborder),
                **cast(
                    CWLObjectType,
                    object_from_state(
                        state,
                        [
                            {**source, **{"type": "Any"}}
                            for source in cast(
                                MutableSequence[CWLObjectType], loop_req.get("loop", [])
                            )
                        ],
                        False,
                        supportsMultipleInput,
                        "loopSource",
                    ),
                ),
            }

            fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)("")

            valueFrom = {
                i["id"]: i["valueFrom"]
                for i in cast(MutableSequence[CWLObjectType], loop_req.get("loop", []))
                if "valueFrom" in i
            }
            if len(valueFrom) > 0 and not bool(
                self.step.step.get_requirement("StepInputExpressionRequirement")[0]
            ):
                raise WorkflowException(
                    "Workflow step contains valueFrom but StepInputExpressionRequirement not in requirements"
                )

            for k, v in inputobj.items():
                if k in valueFrom:
                    adjustDirObjs(
                        v, functools.partial(get_listing, fs_access, recursive=True)
                    )
                    inputobj[k] = cast(
                        CWLObjectType,
                        expression.do_eval(
                            valueFrom[k],
                            {
                                shortname(k): v
                                for k, v in cast(CWLObjectType, self.joborder).items()
                            },
                            self.step.step.requirements,
                            None,
                            None,
                            {},
                            context=v,
                            debug=runtimeContext.debug,
                            js_console=runtimeContext.js_console,
                            timeout=runtimeContext.eval_timeout,
                            container_engine=self.container_engine,
                        ),
                    )
            self.joborder = inputobj
        except Exception:
            self.processStatus = "permanentFail"
            raise
