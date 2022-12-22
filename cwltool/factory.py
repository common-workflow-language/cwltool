import os
from typing import Any, Dict, Optional, Union

from . import load_tool
from .context import LoadingContext, RuntimeContext
from .errors import WorkflowException
from .executors import JobExecutor, SingleJobExecutor
from .process import Process
from .utils import CWLObjectType


class WorkflowStatus(Exception):
    def __init__(self, out: Optional[CWLObjectType], status: str) -> None:
        """Signaling exception for the status of a Workflow."""
        super().__init__("Completed %s" % status)
        self.out = out
        self.status = status


class Callable:
    """Result of ::py:func:`Factory.make`."""

    def __init__(self, t: Process, factory: "Factory") -> None:
        """Initialize."""
        self.t = t
        self.factory = factory

    def __call__(self, **kwargs):
        # type: (**Any) -> Union[str, Optional[CWLObjectType]]
        runtime_context = self.factory.runtime_context.copy()
        runtime_context.basedir = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, runtime_context)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out


class Factory:
    """Easy way to load a CWL document for execution."""

    loading_context: LoadingContext
    runtime_context: RuntimeContext

    def __init__(
        self,
        executor: Optional[JobExecutor] = None,
        loading_context: Optional[LoadingContext] = None,
        runtime_context: Optional[RuntimeContext] = None,
    ) -> None:
        if executor is None:
            executor = SingleJobExecutor()
        self.executor = executor
        if runtime_context is None:
            self.runtime_context = RuntimeContext()
        else:
            self.runtime_context = runtime_context
        if loading_context is None:
            self.loading_context = LoadingContext()
            self.loading_context.singularity = self.runtime_context.singularity
            self.loading_context.podman = self.runtime_context.podman
        else:
            self.loading_context = loading_context

    def make(self, cwl: Union[str, Dict[str, Any]]) -> Callable:
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loading_context)
        if isinstance(load, int):
            raise WorkflowException("Error loading tool")
        return Callable(load, self)
