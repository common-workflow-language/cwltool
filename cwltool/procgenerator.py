import copy
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)

from schema_salad import validate
from schema_salad.sourceline import indent

from .context import LoadingContext, RuntimeContext
from .errors import WorkflowException
from .load_tool import load_tool
from .loghandler import _logger
from .process import Process, shortname


class ProcessGeneratorJob(object):
    def __init__(self, procgenerator):
        # type: (ProcessGenerator) -> None
        self.procgenerator = procgenerator
        self.jobout = None  # type: Optional[Dict[str, Any]]
        self.processStatus = None  # type: Optional[str]

    def receive_output(self, jobout, processStatus):
        # type: (Dict[str, Any], str) -> None
        self.jobout = jobout
        self.processStatus = processStatus

    def job(
        self,
        job_order,  # type: Mapping[str, Any]
        output_callbacks,  # type: Callable[[Any, Any], Any]
        runtimeContext,  # type: RuntimeContext
    ):  # type: (...) -> Generator[Any, None, None]
        # FIXME: Declare base type for what Generator yields

        try:
            for tool in self.procgenerator.embedded_tool.job(
                job_order, self.receive_output, runtimeContext
            ):
                yield tool

            while self.processStatus is None:
                yield None

            if self.processStatus != "success":
                output_callbacks(self.jobout, self.processStatus)
                return

            if self.jobout is None:
                raise WorkflowException("jobout should not be None")

            created_tool, runinputs = self.procgenerator.result(
                job_order, self.jobout, runtimeContext
            )

            for tool in created_tool.job(runinputs, output_callbacks, runtimeContext):
                yield tool

        except WorkflowException:
            raise
        except Exception as exc:
            _logger.exception("Unexpected exception")
            raise WorkflowException(str(exc))


class ProcessGenerator(Process):
    def __init__(
        self,
        toolpath_object,  # type: MutableMapping[str, Any]
        loadingContext,  # type: LoadingContext
    ):  # type: (...) -> None
        super(ProcessGenerator, self).__init__(toolpath_object, loadingContext)
        self.loadingContext = loadingContext  # type: LoadingContext
        try:
            if isinstance(toolpath_object["run"], MutableMapping):
                self.embedded_tool = loadingContext.construct_tool_object(
                    toolpath_object["run"], loadingContext
                )  # type: Process
            else:
                loadingContext.metadata = {}
                self.embedded_tool = load_tool(toolpath_object["run"], loadingContext)
        except validate.ValidationException as vexc:
            if loadingContext.debug:
                _logger.exception("Validation exception")
            raise WorkflowException(
                "Tool definition %s failed validation:\n%s"
                % (toolpath_object["run"], indent(str(vexc)))
            )

    def job(
        self,
        job_order,  # type: Mapping[str, str]
        output_callbacks,  # type: Callable[[Any, Any], Any]
        runtimeContext,  # type: RuntimeContext
    ):  # type: (...) -> Generator[Any, None, None]
        # FIXME: Declare base type for what Generator yields
        return ProcessGeneratorJob(self).job(
            job_order, output_callbacks, runtimeContext
        )

    def result(
        self,
        job_order,  # type: Mapping[str, Any]
        jobout,  # type: Mapping[str, Any]
        runtimeContext,  # type: RuntimeContext
    ):  # type: (...) -> Tuple[Process, MutableMapping[str, Any]]
        try:
            loadingContext = self.loadingContext.copy()
            loadingContext.metadata = {}
            embedded_tool = load_tool(jobout["runProcess"]["location"], loadingContext)
        except validate.ValidationException as vexc:
            if runtimeContext.debug:
                _logger.exception("Validation exception")
            raise WorkflowException(
                "Tool definition %s failed validation:\n%s"
                % (jobout["runProcess"], indent(str(vexc)))
            )

        if "runInputs" in jobout:
            runinputs = cast(MutableMapping[str, Any], jobout["runInputs"])
        else:
            runinputs = cast(MutableMapping[str, Any], copy.deepcopy(job_order))
            for i in self.embedded_tool.tool["inputs"]:
                if shortname(i["id"]) in runinputs:
                    del runinputs[shortname(i["id"])]
            if "id" in runinputs:
                del runinputs["id"]

        return embedded_tool, runinputs
