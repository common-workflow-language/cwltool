"""Tests for customising the PathMapper used to stage a CommandLineTool's inputs.

Two extension points are exercised:

* setting :py:attr:`RuntimeContext.path_mapper` (like ``make_fs_access``), and
* overriding :py:meth:`CommandLineTool.make_path_mapper` in a subclass.
"""

from collections.abc import MutableSequence
from typing import cast

from cwl_utils.types import CWLDirectoryType, CWLFileType
from ruamel.yaml.comments import CommentedMap
from schema_salad.sourceline import cmap

from cwltool.command_line_tool import CommandLineTool, default_make_path_mapper
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.job import JobBase
from cwltool.pathmapper import PathMapper
from cwltool.update import INTERNAL_VERSION, ORIGINAL_CWLVERSION


class CustomPathMapper(PathMapper):
    """A trivial PathMapper subclass used as a sentinel in these tests."""


def _make_clt(cls: type[CommandLineTool] = CommandLineTool) -> CommandLineTool:
    """Build a minimal no-op CommandLineTool for exercising ``.job()``."""
    loading_context = LoadingContext(
        {
            "metadata": {
                "cwlVersion": INTERNAL_VERSION,
                ORIGINAL_CWLVERSION: INTERNAL_VERSION,
            }
        }
    )
    return cls(
        cast(
            CommentedMap,
            cmap(
                {
                    "cwlVersion": INTERNAL_VERSION,
                    "class": "CommandLineTool",
                    "inputs": [],
                    "outputs": [],
                    "requirements": [],
                }
            ),
        ),
        loading_context,
    )


def _first_job(clt: CommandLineTool, runtime_context: RuntimeContext) -> JobBase:
    """Return the first job produced by ``clt.job`` (without running it)."""
    job = next(clt.job({}, lambda output, process_status: None, runtime_context))
    assert isinstance(job, JobBase)
    return job


def test_default_make_path_mapper_returns_plain_pathmapper() -> None:
    """Without customisation the default factory builds a plain PathMapper."""
    mapper = default_make_path_mapper([], "", RuntimeContext(), True)
    assert type(mapper) is PathMapper


def test_default_make_path_mapper_honours_runtime_context() -> None:
    """default_make_path_mapper uses RuntimeContext.path_mapper, like make_fs_access."""
    runtime_context = RuntimeContext()
    runtime_context.path_mapper = CustomPathMapper
    mapper = default_make_path_mapper([], "", runtime_context, True)
    assert isinstance(mapper, CustomPathMapper)


def test_runtime_context_path_mapper_used_for_input_staging() -> None:
    """A custom RuntimeContext.path_mapper is used when a job stages its inputs."""
    runtime_context = RuntimeContext()
    runtime_context.path_mapper = CustomPathMapper
    job = _first_job(_make_clt(), runtime_context)
    assert isinstance(job.builder.pathmapper, CustomPathMapper)


def test_subclass_can_override_make_path_mapper() -> None:
    """Overriding CommandLineTool.make_path_mapper in a subclass takes effect."""

    class SubclassPathMapper(PathMapper):
        pass

    class CustomCommandLineTool(CommandLineTool):
        def make_path_mapper(
            self,
            reffiles: MutableSequence[CWLFileType | CWLDirectoryType],
            stagedir: str,
            runtimeContext: RuntimeContext,
            separateDirs: bool,
        ) -> PathMapper:
            return SubclassPathMapper(reffiles, runtimeContext.basedir, stagedir, separateDirs)

    job = _first_job(_make_clt(CustomCommandLineTool), RuntimeContext())
    assert isinstance(job.builder.pathmapper, SubclassPathMapper)
