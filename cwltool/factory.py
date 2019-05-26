from __future__ import absolute_import

# move to a regular typing import when Python 3.3-3.6 is no longer supported
import functools
import os
import sys
from typing import Callable as tCallable  # pylint: disable=unused-import
from typing import Any, Dict, Tuple, Union

from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import load_tool
from .argparser import arg_parser
from .context import LoadingContext, RuntimeContext, getdefault
from .executors import SingleJobExecutor
from .main import find_default_container
from .resolver import tool_resolver
from .secrets import SecretStore
from .utils import DEFAULT_TMP_PREFIX


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
        out, status = self.factory.executor(
            self.t, kwargs, self.factory.runtimeContext)
        if status != "success":
            raise WorkflowStatus(out, status)
        else:
            return out


class Factory(object):
    def __init__(self,
                 argsl=None,                   # type: List[str]
                 args=None,                    # type: argparse.Namespace
                 executor=None,                # type: Callable[..., Tuple[Dict[Text, Any], Text]]
                 loadingContext=None,          # type: LoadingContext
                 runtimeContext=None           # type: RuntimeContext
                 ):  # type: (...) -> None
        if argsl is not None:
            args = arg_parser().parse_args(argsl)
        if executor is None:
            self.executor = SingleJobExecutor()
        else:
            self.executor = executor
        if loadingContext is None:
            self.loadingContext = LoadingContext(vars(args))
            self._fix_loadingContext()
        else:
            self.loadingContext = loadingContext
        if runtimeContext is None:
            self.runtimeContext = RuntimeContext(vars(args))
            self._fix_runtimeContext()
        else:
            self.runtimeContext = runtimeContext

    def make(self, cwl):
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loadingContext)
        if isinstance(load, int):
            raise Exception("Error loading tool")
        return Callable(load, self)

    def _fix_loadingContext(self):
        self.loadingContext.resolver = getdefault(
            self.loadingContext.resolver, tool_resolver)

    def _fix_runtimeContext(self):
        self.runtimeContext.basedir = os.getcwd()
        self.runtimeContext.find_default_container = functools.partial(
            find_default_container,
            default_container=None,
            use_biocontainers=None)

        if sys.platform == "darwin":
            default_mac_path = "/private/tmp/docker_tmp"
            if self.runtimeContext.tmp_outdir_prefix == DEFAULT_TMP_PREFIX:
                self.runtimeContext.tmp_outdir_prefix = default_mac_path

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if getattr(self.runtimeContext, dirprefix) and getattr(self.runtimeContext, dirprefix) != DEFAULT_TMP_PREFIX:
                sl = "/" if getattr(self.runtimeContext, dirprefix).endswith("/") or dirprefix == "cachedir" \
                    else ""
                setattr(self.runtimeContext, dirprefix,
                        os.path.abspath(getattr(self.runtimeContext, dirprefix)) + sl)
                if not os.path.exists(os.path.dirname(getattr(self.runtimeContext, dirprefix))):
                    try:
                        os.makedirs(os.path.dirname(
                            getattr(self.runtimeContext, dirprefix)))
                    except Exception as e:
                        print("Failed to create directory: %s", e)

        self.runtimeContext.secret_store = getdefault(
            self.runtimeContext.secret_store, SecretStore())
