from __future__ import absolute_import
import os
from typing import Callable as tCallable
from typing import Any, Dict, Text, Tuple, Union

from . import load_tool, workflow
from .argparser import get_default_args
from .executors import SingleJobExecutor
from .process import Process


class WorkflowStatus(Exception):
    def __init__(self, out, status):
        # type: (Dict[Text,Any], Text) -> None
        super(WorkflowStatus, self).__init__("Completed %s" % status)
        self.out = out
        self.status = status


class Callable(object):
    def __init__(self, t, factory):  # type: (Process, Factory) -> None
        self.t = t
        self.factory = factory

    def __call__(self, **kwargs):
        # type: (**Any) -> Union[Text, Dict[Text, Text]]
        execkwargs = self.factory.execkwargs.copy()
        execkwargs["basedir"] = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, **execkwargs)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out


class Factory(object):
    def __init__(self,
                 makeTool=workflow.defaultMakeTool,  # type: tCallable[[Any], Process]
                 # should be tCallable[[Dict[Text, Any], Any], Process] ?
                 executor=None,  # type: tCallable[...,Tuple[Dict[Text,Any], Text]]
                 **execkwargs  # type: Any
                 ):
        # type: (...) -> None
        self.makeTool = makeTool
        if executor is None:
            executor = SingleJobExecutor()
        self.executor = executor

        kwargs = get_default_args()
        kwargs.pop("job_order")
        kwargs.pop("workflow")
        kwargs.pop("outdir")
        kwargs.update(execkwargs)
        self.execkwargs = kwargs

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.makeTool)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
