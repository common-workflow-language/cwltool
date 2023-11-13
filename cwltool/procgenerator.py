import copy
from typing import Dict, Optional, Tuple, cast

from ruamel.yaml.comments import CommentedMap
from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import indent

from .context import LoadingContext, RuntimeContext
from .errors import WorkflowException
from .load_tool import load_tool
from .loghandler import _logger
from .process import Process, shortname
from .utils import CWLObjectType, JobsGeneratorType, OutputCallbackType


class ProcessGeneratorJob:
    """Result of ProcessGenerator.job()."""

    def __init__(self, procgenerator: "ProcessGenerator") -> None:
        """Create a ProccessGenerator Job."""
        self.procgenerator = procgenerator
        self.jobout = None  # type: Optional[CWLObjectType]
        self.processStatus = None  # type: Optional[str]

    def receive_output(self, jobout: Optional[CWLObjectType], processStatus: str) -> None:
        """Process the results."""
        self.jobout = jobout
        self.processStatus = processStatus

    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        try:
            yield from self.procgenerator.embedded_tool.job(
                job_order, self.receive_output, runtimeContext
            )

            while self.processStatus is None:
                yield None

            if self.processStatus != "success" and output_callbacks:
                output_callbacks(self.jobout, self.processStatus)
                return

            if self.jobout is None:
                raise WorkflowException("jobout should not be None")

            created_tool, runinputs = self.procgenerator.result(
                job_order, self.jobout, runtimeContext
            )

            yield from created_tool.job(runinputs, output_callbacks, runtimeContext)

        except WorkflowException:
            raise
        except Exception as exc:
            _logger.exception("Unexpected exception")
            raise WorkflowException(str(exc)) from exc


class ProcessGenerator(Process):
    def __init__(
        self,
        toolpath_object: CommentedMap,
        loadingContext: LoadingContext,
    ) -> None:
        """Create a ProcessGenerator from the given dictionary and context."""
        super().__init__(toolpath_object, loadingContext)
        self.loadingContext = loadingContext  # type: LoadingContext
        try:
            if isinstance(toolpath_object["run"], CommentedMap):
                self.embedded_tool = loadingContext.construct_tool_object(
                    toolpath_object["run"], loadingContext
                )  # type: Process
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

    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        return ProcessGeneratorJob(self).job(job_order, output_callbacks, runtimeContext)

    def result(
        self,
        job_order: CWLObjectType,
        jobout: CWLObjectType,
        runtimeContext: RuntimeContext,
    ) -> Tuple[Process, CWLObjectType]:
        try:
            loadingContext = self.loadingContext.copy()
            loadingContext.metadata = {}
            embedded_tool = load_tool(
                cast(Dict[str, str], jobout["runProcess"])["location"], loadingContext
            )
        except ValidationException as vexc:
            if runtimeContext.debug:
                _logger.exception("Validation exception")
            raise WorkflowException(
                "Tool definition %s failed validation:\n%s"
                % (jobout["runProcess"], indent(str(vexc)))
            ) from vexc

        if "runInputs" in jobout:
            runinputs = cast(CWLObjectType, jobout["runInputs"])
        else:
            runinputs = copy.deepcopy(job_order)
            for i in self.embedded_tool.tool["inputs"]:
                if shortname(i["id"]) in runinputs:
                    del runinputs[shortname(i["id"])]
            if "id" in runinputs:
                del runinputs["id"]

        return embedded_tool, runinputs
