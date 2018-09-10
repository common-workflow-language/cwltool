from __future__ import absolute_import

import os
from typing import Callable as tCallable  # pylint: disable=unused-import
from typing import Any, Dict, Tuple, Union

from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import load_tool
from .context import LoadingContext, RuntimeContext
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
        runtime_context = self.factory.runtime_context.copy()
        runtime_context.basedir = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, runtime_context)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out

class Factory(object):
    def __init__(self,
                 executor=None,        # type: tCallable[...,Tuple[Dict[Text,Any], Text]]
                 loading_context=None,  # type: LoadingContext
                 runtime_context=None   # type: RuntimeContext
                ):  # type: (...) -> None
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

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loading_context)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
