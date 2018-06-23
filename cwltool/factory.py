from __future__ import absolute_import

import os
from typing import Callable as tCallable # pylint: disable=unused-import
from typing import (Any, # pylint: disable=unused-import
                    Dict, Optional, Text, Tuple, Union)

from . import load_tool
from .argparser import get_default_args
from .executors import SingleJobExecutor
from .process import Process
from .software_requirements import (  # pylint: disable=unused-import
    DependenciesConfiguration)
from .workflow import default_make_tool
from .context import LoadingContext, RuntimeContext, getdefault

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
        runtimeContext = self.factory.runtimeContext.copy()
        runtimeContext.basedir = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, runtimeContext)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out

class Factory(object):
    def __init__(self,
                 executor=None,            # type: tCallable[...,Tuple[Dict[Text,Any], Text]]
                 loadingContext=None,      # type: LoadingContext
                 runtimeContext=None,      # type: RuntimeContext
                 **kwargs
                ):  # type: (...) -> None
        if executor is None:
            executor = SingleJobExecutor()
        self.executor = executor

        new_exec_kwargs = get_default_args()
        new_exec_kwargs.update(kwargs)
        new_exec_kwargs.pop("job_order")
        new_exec_kwargs.pop("workflow")
        new_exec_kwargs.pop("outdir")

        if loadingContext is None:
            self.loadingContext = LoadingContext(new_exec_kwargs)
        else:
            self.loadingContext = loadingContext

        if runtimeContext is None:
            self.runtimeContext = RuntimeContext(new_exec_kwargs)
        else:
            self.runtimeContext = runtimeContext

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loadingContext)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
