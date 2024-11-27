"""Wrap a CWL document as a callable Python object."""

import argparse
import functools
import os
import sys
from typing import Any, Optional, Union

from . import load_tool
from .argparser import arg_parser
from .context import LoadingContext, RuntimeContext, getdefault
from .errors import WorkflowException
from .executors import JobExecutor, SingleJobExecutor
from .main import find_default_container
from .process import Process
from .resolver import tool_resolver
from .secrets import SecretStore
from .utils import DEFAULT_TMP_PREFIX, CWLObjectType


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

    def __call__(self, **kwargs: Any) -> Union[str, Optional[CWLObjectType]]:
        """
        Execute the process.

        :raise WorkflowStatus: If the result is not a success.
        """
        if not self.factory.runtime_context.basedir:
            self.factory.runtime_context.basedir = os.getcwd()
        out, status = self.factory.executor(self.t, kwargs, self.factory.runtime_context)
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
        argsl: Optional[list[str]] = None,
        args: Optional[argparse.Namespace] = None,
    ) -> None:
        """Create a CWL Process factory from a CWL document."""
        if argsl is not None:
            args = arg_parser().parse_args(argsl)
        if executor is None:
            self.executor: JobExecutor = SingleJobExecutor()
        else:
            self.executor = executor
        if runtime_context is None:
            self.runtime_context = RuntimeContext(vars(args) if args else {})
            self._fix_runtime_context()
        else:
            self.runtime_context = runtime_context
        if loading_context is None:
            self.loading_context = LoadingContext(vars(args) if args else {})
            self._fix_loading_context(self.runtime_context)
        else:
            self.loading_context = loading_context

    def make(self, cwl: Union[str, dict[str, Any]]) -> Callable:
        """Instantiate a CWL object from a CWl document."""
        load = load_tool.load_tool(cwl, self.loading_context)
        if isinstance(load, int):
            raise WorkflowException("Error loading tool")
        return Callable(load, self)

    def _fix_loading_context(self, runtime_context: RuntimeContext) -> None:
        self.loading_context.resolver = getdefault(self.loading_context.resolver, tool_resolver)
        self.loading_context.singularity = runtime_context.singularity
        self.loading_context.podman = runtime_context.podman

    def _fix_runtime_context(self) -> None:
        self.runtime_context.basedir = os.getcwd()
        self.runtime_context.find_default_container = functools.partial(
            find_default_container, default_container=None, use_biocontainers=None
        )

        if sys.platform == "darwin":
            default_mac_path = "/private/tmp/docker_tmp"
            if self.runtime_context.tmp_outdir_prefix == DEFAULT_TMP_PREFIX:
                self.runtime_context.tmp_outdir_prefix = default_mac_path

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if (
                getattr(self.runtime_context, dirprefix)
                and getattr(self.runtime_context, dirprefix) != DEFAULT_TMP_PREFIX
            ):
                sl = (
                    "/"
                    if getattr(self.runtime_context, dirprefix).endswith("/")
                    or dirprefix == "cachedir"
                    else ""
                )
                setattr(
                    self.runtime_context,
                    dirprefix,
                    os.path.abspath(getattr(self.runtime_context, dirprefix)) + sl,
                )
                if not os.path.exists(os.path.dirname(getattr(self.runtime_context, dirprefix))):
                    try:
                        os.makedirs(os.path.dirname(getattr(self.runtime_context, dirprefix)))
                    except Exception as e:
                        print("Failed to create directory: %s", e)

        self.runtime_context.secret_store = getdefault(
            self.runtime_context.secret_store, SecretStore()
        )
