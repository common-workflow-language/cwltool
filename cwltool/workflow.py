import copy
import datetime
import functools
import logging
import random
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Union,
    cast,
)
from uuid import UUID

from mypy_extensions import mypyc_attr
from ruamel.yaml.comments import CommentedMap
from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import SourceLine, indent

from . import command_line_tool, context, procgenerator
from .checker import circular_dependency_checker, loop_checker, static_checker
from .context import LoadingContext, RuntimeContext, getdefault
from .cwlprov.provenance_profile import ProvenanceProfile
from .cwlprov.writablebagfile import create_job
from .errors import WorkflowException
from .load_tool import load_tool
from .loghandler import _logger
from .process import Process, get_overrides, shortname
from .utils import (
    CWLObjectType,
    CWLOutputType,
    JobsGeneratorType,
    OutputCallbackType,
    StepType,
    aslist,
)
from .workflow_job import WorkflowJob


def default_make_tool(toolpath_object: CommentedMap, loadingContext: LoadingContext) -> Process:
    """Instantiate the given CWL Process."""
    if not isinstance(toolpath_object, MutableMapping):
        raise WorkflowException("Not a dict: '%s'" % toolpath_object)
    if "class" in toolpath_object:
        if toolpath_object["class"] == "CommandLineTool":
            return command_line_tool.CommandLineTool(toolpath_object, loadingContext)
        if toolpath_object["class"] == "ExpressionTool":
            return command_line_tool.ExpressionTool(toolpath_object, loadingContext)
        if toolpath_object["class"] == "Workflow":
            return Workflow(toolpath_object, loadingContext)
        if toolpath_object["class"] == "ProcessGenerator":
            return procgenerator.ProcessGenerator(toolpath_object, loadingContext)
        if toolpath_object["class"] == "Operation":
            return command_line_tool.AbstractOperation(toolpath_object, loadingContext)

    raise WorkflowException(
        "Missing or invalid 'class' field in "
        "%s, expecting one of: CommandLineTool, ExpressionTool, Workflow" % toolpath_object["id"]
    )


context.default_make_tool = default_make_tool


@mypyc_attr(serializable=True)
class Workflow(Process):
    def __init__(
        self,
        toolpath_object: CommentedMap,
        loadingContext: LoadingContext,
    ) -> None:
        """Initialize this Workflow."""
        super().__init__(toolpath_object, loadingContext)
        self.provenance_object: Optional[ProvenanceProfile] = None
        if loadingContext.research_obj is not None:
            run_uuid: Optional[UUID] = None
            is_main = not loadingContext.prov_obj  # Not yet set
            if is_main:
                run_uuid = loadingContext.research_obj.ro_uuid

            self.provenance_object = ProvenanceProfile(
                loadingContext.research_obj,
                full_name=loadingContext.cwl_full_name,
                host_provenance=loadingContext.host_provenance,
                user_provenance=loadingContext.user_provenance,
                orcid=loadingContext.orcid,
                run_uuid=run_uuid,
                fsaccess=loadingContext.research_obj.fsaccess,
            )  # inherit RO UUID for main wf run
            # TODO: Is Workflow(..) only called when we are the main workflow?
            self.parent_wf = self.provenance_object

        # FIXME: Won't this overwrite prov_obj for nested workflows?
        loadingContext.prov_obj = self.provenance_object
        loadingContext = loadingContext.copy()
        loadingContext.requirements = self.requirements
        loadingContext.hints = self.hints

        self.steps: List[WorkflowStep] = []
        validation_errors = []
        for index, step in enumerate(self.tool.get("steps", [])):
            try:
                self.steps.append(
                    self.make_workflow_step(step, index, loadingContext, loadingContext.prov_obj)
                )
            except ValidationException as vexc:
                if _logger.isEnabledFor(logging.DEBUG):
                    _logger.exception("Validation failed at")
                validation_errors.append(vexc)

        if validation_errors:
            raise ValidationException("\n".join(str(v) for v in validation_errors))

        random.shuffle(self.steps)

        # statically validate data links instead of doing it at runtime.
        workflow_inputs = self.tool["inputs"]
        workflow_outputs = self.tool["outputs"]

        step_inputs: List[CWLObjectType] = []
        step_outputs: List[CWLObjectType] = []
        param_to_step: Dict[str, CWLObjectType] = {}
        for step in self.steps:
            step_inputs.extend(step.tool["inputs"])
            step_outputs.extend(step.tool["outputs"])
            for s in step.tool["inputs"]:
                param_to_step[s["id"]] = step.tool
            for s in step.tool["outputs"]:
                param_to_step[s["id"]] = step.tool

        if getdefault(loadingContext.do_validate, True):
            static_checker(
                workflow_inputs,
                workflow_outputs,
                step_inputs,
                step_outputs,
                param_to_step,
            )
            circular_dependency_checker(step_inputs)
            loop_checker(step.tool for step in self.steps)

    def make_workflow_step(
        self,
        toolpath_object: CommentedMap,
        pos: int,
        loadingContext: LoadingContext,
        parentworkflowProv: Optional[ProvenanceProfile] = None,
    ) -> "WorkflowStep":
        return WorkflowStep(toolpath_object, pos, loadingContext, parentworkflowProv)

    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        builder = self._init_job(job_order, runtimeContext)

        if runtimeContext.research_obj is not None:
            if runtimeContext.toplevel:
                # Record primary-job.json
                runtimeContext.research_obj.fsaccess = runtimeContext.make_fs_access("")
                create_job(runtimeContext.research_obj, builder.job)

        job = WorkflowJob(self, runtimeContext)
        yield job

        runtimeContext = runtimeContext.copy()
        runtimeContext.part_of = "workflow %s" % job.name
        runtimeContext.toplevel = False

        yield from job.job(builder.job, output_callbacks, runtimeContext)

    def visit(self, op: Callable[[CommentedMap], None]) -> None:
        op(self.tool)
        for step in self.steps:
            step.visit(op)


def used_by_step(step: StepType, shortinputid: str) -> bool:
    for st in cast(MutableSequence[CWLObjectType], step["in"]):
        if st.get("valueFrom"):
            if ("inputs.%s" % shortinputid) in cast(str, st.get("valueFrom")):
                return True
    if step.get("when"):
        if ("inputs.%s" % shortinputid) in cast(str, step.get("when")):
            return True
    return False


class WorkflowStep(Process):
    def __init__(
        self,
        toolpath_object: CommentedMap,
        pos: int,
        loadingContext: LoadingContext,
        parentworkflowProv: Optional[ProvenanceProfile] = None,
    ) -> None:
        """Initialize this WorkflowStep."""
        debug = loadingContext.debug
        if "id" in toolpath_object:
            self.id = toolpath_object["id"]
        else:
            self.id = "#step" + str(pos)

        loadingContext = loadingContext.copy()

        parent_requirements = copy.deepcopy(getdefault(loadingContext.requirements, []))
        loadingContext.requirements = copy.deepcopy(toolpath_object.get("requirements", []))
        assert loadingContext.requirements is not None  # nosec
        for parent_req in parent_requirements:
            found_in_step = False
            for step_req in loadingContext.requirements:
                if parent_req["class"] == step_req["class"]:
                    found_in_step = True
                    break
            if not found_in_step and parent_req.get("class") != "http://commonwl.org/cwltool#Loop":
                loadingContext.requirements.append(parent_req)
        loadingContext.requirements.extend(
            cast(
                List[CWLObjectType],
                get_overrides(getdefault(loadingContext.overrides_list, []), self.id).get(
                    "requirements", []
                ),
            )
        )

        hints = copy.deepcopy(getdefault(loadingContext.hints, []))
        hints.extend(toolpath_object.get("hints", []))
        loadingContext.hints = hints

        try:
            if isinstance(toolpath_object["run"], CommentedMap):
                self.embedded_tool: Process = loadingContext.construct_tool_object(
                    toolpath_object["run"], loadingContext
                )
            else:
                loadingContext.metadata = {}
                self.embedded_tool = load_tool(toolpath_object["run"], loadingContext)
        except ValidationException as vexc:
            if loadingContext.debug:
                _logger.exception("Validation exception")
            raise WorkflowException(
                "Tool definition %s failed validation:\n%s"
                % (toolpath_object["run"], indent(str(vexc)))
            ) from vexc

        validation_errors = []
        self.tool = toolpath_object = copy.deepcopy(toolpath_object)
        bound = set()

        if self.embedded_tool.get_requirement("SchemaDefRequirement")[0]:
            if "requirements" not in toolpath_object:
                toolpath_object["requirements"] = []
            toolpath_object["requirements"].append(
                self.embedded_tool.get_requirement("SchemaDefRequirement")[0]
            )

        for stepfield, toolfield in (("in", "inputs"), ("out", "outputs")):
            toolpath_object[toolfield] = []
            for index, step_entry in enumerate(toolpath_object[stepfield]):
                if isinstance(step_entry, str):
                    param: CommentedMap = CommentedMap()
                    inputid = step_entry
                else:
                    param = CommentedMap(step_entry.items())
                    inputid = step_entry["id"]

                shortinputid = shortname(inputid)
                found = False
                for tool_entry in self.embedded_tool.tool[toolfield]:
                    frag = shortname(tool_entry["id"])
                    if frag == shortinputid:
                        # if the case that the step has a default for a parameter,
                        # we do not want the default of the tool to override it
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
                        param["used_by_step"] = used_by_step(self.tool, shortinputid)
                        param["not_connected"] = True
                    else:
                        if isinstance(step_entry, Mapping):
                            step_entry_name = step_entry["id"]
                        else:
                            step_entry_name = step_entry
                        validation_errors.append(
                            SourceLine(self.tool["out"], index, include_traceback=debug).makeError(
                                "Workflow step output '%s' does not correspond to"
                                % shortname(step_entry_name)
                            )
                            + "\n"
                            + SourceLine(
                                self.embedded_tool.tool,
                                "outputs",
                                include_traceback=debug,
                            ).makeError(
                                "  tool output (expected '%s')"
                                % (
                                    "', '".join(
                                        [
                                            shortname(tool_entry["id"])
                                            for tool_entry in self.embedded_tool.tool["outputs"]
                                        ]
                                    )
                                )
                            )
                        )
                param["id"] = inputid
                param.lc.line = toolpath_object[stepfield].lc.data[index][0]
                param.lc.col = toolpath_object[stepfield].lc.data[index][1]
                param.lc.filename = toolpath_object[stepfield].lc.filename
                toolpath_object[toolfield].append(param)

        missing_values = []
        for _, tool_entry in enumerate(self.embedded_tool.tool["inputs"]):
            if shortname(tool_entry["id"]) not in bound:
                if "null" not in tool_entry["type"] and "default" not in tool_entry:
                    missing_values.append(shortname(tool_entry["id"]))

        if missing_values:
            validation_errors.append(
                SourceLine(self.tool, "in", include_traceback=debug).makeError(
                    "Step is missing required parameter%s '%s'"
                    % (
                        "s" if len(missing_values) > 1 else "",
                        "', '".join(missing_values),
                    )
                )
            )

        if validation_errors:
            raise ValidationException("\n".join(validation_errors))

        super().__init__(toolpath_object, loadingContext)

        if self.embedded_tool.tool["class"] == "Workflow":
            (feature, _) = self.get_requirement("SubworkflowFeatureRequirement")
            if not feature:
                raise WorkflowException(
                    "Workflow contains embedded workflow but "
                    "SubworkflowFeatureRequirement not in requirements"
                )

        if "scatter" in self.tool:
            (feature, _) = self.get_requirement("ScatterFeatureRequirement")
            if not feature:
                raise WorkflowException(
                    "Workflow contains scatter but ScatterFeatureRequirement " "not in requirements"
                )

            inputparms = copy.deepcopy(self.tool["inputs"])
            outputparms = copy.deepcopy(self.tool["outputs"])
            scatter = aslist(self.tool["scatter"])

            method = self.tool.get("scatterMethod")
            if method is None and len(scatter) != 1:
                raise ValidationException(
                    "Must specify scatterMethod when scattering over multiple inputs"
                )

            inp_map = {i["id"]: i for i in inputparms}
            for inp in scatter:
                if inp not in inp_map:
                    SourceLine(self.tool, "scatter", ValidationException, debug).makeError(
                        "Scatter parameter '%s' does not correspond to "
                        "an input parameter of this step, expecting '%s'"
                        % (
                            shortname(inp),
                            "', '".join(shortname(k) for k in inp_map.keys()),
                        )
                    )

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
        self.prov_obj: Optional[ProvenanceProfile] = None
        if loadingContext.research_obj is not None:
            self.prov_obj = parentworkflowProv
            if self.embedded_tool.tool["class"] == "Workflow":
                self.parent_wf = self.embedded_tool.parent_wf
            else:
                self.parent_wf = self.prov_obj

    def checkRequirements(
        self,
        rec: Union[MutableSequence[CWLObjectType], CWLObjectType, CWLOutputType, None],
        supported_process_requirements: Iterable[str],
    ) -> None:
        """Check the presence of unsupported requirements."""
        supported_process_requirements = list(supported_process_requirements)
        supported_process_requirements.append("http://commonwl.org/cwltool#Loop")
        super().checkRequirements(rec, supported_process_requirements)

    def receive_output(
        self,
        output_callback: OutputCallbackType,
        jobout: CWLObjectType,
        processStatus: str,
    ) -> None:
        output = {}
        for i in self.tool["outputs"]:
            field = shortname(i["id"])
            if field in jobout:
                output[i["id"]] = jobout[field]
            else:
                processStatus = "permanentFail"
        output_callback(output, processStatus)

    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        """Initialize sub-workflow as a step in the parent profile."""
        if (
            self.embedded_tool.tool["class"] == "Workflow"
            and runtimeContext.research_obj
            and self.prov_obj
            and self.embedded_tool.provenance_object
        ):
            self.embedded_tool.parent_wf = self.prov_obj
            process_name = self.tool["id"].split("#")[1]
            self.prov_obj.start_process(
                process_name,
                datetime.datetime.now(),
                self.embedded_tool.provenance_object.workflow_run_uri,
            )

        step_input = {}
        for inp in self.tool["inputs"]:
            field = shortname(inp["id"])
            if not inp.get("not_connected"):
                step_input[field] = job_order[inp["id"]]

        try:
            yield from self.embedded_tool.job(
                step_input,
                functools.partial(self.receive_output, output_callbacks),
                runtimeContext,
            )
        except WorkflowException:
            _logger.error("Exception on step '%s'", runtimeContext.name)
            raise
        except Exception as exc:
            _logger.exception("Unexpected exception")
            raise WorkflowException(str(exc)) from exc

    def visit(self, op: Callable[[CommentedMap], None]) -> None:
        self.embedded_tool.visit(op)
