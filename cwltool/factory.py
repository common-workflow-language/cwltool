from . import main
from . import load_tool
from . import workflow
import os
from .process import Process
from typing import Any, Union
from typing import Callable as tCallable
import argparse

class Callable(object):
    def __init__(self, t, factory):  # type: (Process, Factory) -> None
        self.t = t
        self.factory = factory

    def __call__(self, **kwargs):  # type: (**Any) -> Union[str,Dict[str,str]]
        execkwargs = self.factory.execkwargs.copy()
        execkwargs["basedir"] = os.getcwd()
        return self.factory.executor(self.t, kwargs, **execkwargs)

class Factory(object):
    def __init__(self, makeTool=workflow.defaultMakeTool,
                 executor=main.single_job_executor,
                 **execkwargs):
        # type: (tCallable[[Dict[str, Any], Any], Process],tCallable[...,Union[str,Dict[str,str]]], **Any) -> None
        self.makeTool = makeTool
        self.executor = executor
        self.execkwargs = execkwargs

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.makeTool)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
