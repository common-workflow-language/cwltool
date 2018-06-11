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
                 make_tool=default_make_tool,  # type: ignore
                 executor=None,            # type: tCallable[...,Tuple[Dict[Text,Any], Text]]
                 eval_timeout=20,          # type: float
                 debug=False,              # type: bool
                 js_console=False,         # type: bool
                 force_docker_pull=False,  # type: bool
                 job_script_provider=None, # type: DependenciesConfiguration
                 makekwargs=None,          # type: Dict[Any, Any]
                 **execkwargs              # type: Dict[Any, Any]
                ):  # type: (...) -> None
        self.make_tool = make_tool
        if executor is None:
            executor = SingleJobExecutor()
        self.executor = executor
        self.eval_timeout = eval_timeout
        self.debug = debug
        self.js_console = js_console
        self.force_docker_pull = force_docker_pull
        self.job_script_provider = job_script_provider

        new_exec_kwargs = get_default_args()
        new_exec_kwargs.pop("job_order")
        new_exec_kwargs.pop("workflow")
        new_exec_kwargs.pop("outdir")
        new_exec_kwargs.update(execkwargs)
        self.execkwargs = new_exec_kwargs
        self.makekwargs = makekwargs if makekwargs is not None else {}

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.make_tool, self.eval_timeout,
                                   self.debug, self.js_console,
                                   self.force_docker_pull,
                                   self.job_script_provider,
                                   strict=self.execkwargs.get("strict", True),
                                   kwargs=self.makekwargs)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)
