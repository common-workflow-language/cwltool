import os
from typing import Any
from typing import Callable as tCallable
from typing import Dict, Optional, Tuple, Union

from . import load_tool
from .context import LoadingContext, RuntimeContext
from .executors import SingleJobExecutor
from .process import Process


class WorkflowStatus(Exception):
    def __init__(self, out, status):
        # type: (Dict[str,Any], str) -> None
        """Signaling exception for the status of a Workflow."""
        super(WorkflowStatus, self).__init__("Completed %s" % status)
        self.out = out
        self.status = status


class Callable(object):
    def __init__(self, t, factory):  # type: (Process, Factory) -> None
        """Initialize."""
        self.t = t
        self.factory = factory

    def __call__(self, **kwargs):
        # type: (**Any) -> Union[str, Dict[str, str]]
        runtime_context = self.factory.runtime_context.copy()
        runtime_context.basedir = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, runtime_context)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out


class Factory(object):
    def __init__(
        self,
        executor: Optional[tCallable[..., Tuple[Dict[str, Any], str]]] = None,
        loading_context: Optional[LoadingContext] = None,
        runtime_context: Optional[RuntimeContext] = None,
    ) -> None:
        """Easy way to load a CWL document for execution."""
        if executor is None:
            executor = SingleJobExecutor()
        self.executor = executor
        self.loading_context = loading_context
        if loading_context is None:
            self.loading_context = LoadingContext()
        if runtime_context is None:
            self.runtime_context = RuntimeContext()
        else:
            self.runtime_context = runtime_context

    def make(self, cwl):  # type: (Union[str, Dict[str, Any]]) -> Callable
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loading_context)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
