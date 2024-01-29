"""Test that files marked as 'streamable' when 'streaming_allowed' can be named pipes."""

import os
from pathlib import Path
from typing import cast

import pytest
from ruamel.yaml.comments import CommentedMap
from schema_salad.sourceline import cmap

from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.job import JobBase
from cwltool.update import INTERNAL_VERSION, ORIGINAL_CWLVERSION
from cwltool.utils import CWLObjectType

from .util import get_data

toolpath_object = cast(
    CommentedMap,
    cmap(
        {
            "cwlVersion": INTERNAL_VERSION,
            "class": "CommandLineTool",
            "inputs": [
                {
                    "type": "File",
                    "id": "inp",
                    "streamable": True,
                }
            ],
            "outputs": [],
            "requirements": [],
        }
    ),
)

loading_context = LoadingContext(
    {
        "metadata": {
            "cwlVersion": INTERNAL_VERSION,
            ORIGINAL_CWLVERSION: INTERNAL_VERSION,
        }
    }
)


def test_regular_file() -> None:
    """Test that regular files do not raise any exception when they are checked in job._setup."""
    clt = CommandLineTool(
        toolpath_object,
        loading_context,
    )
    runtime_context = RuntimeContext()

    joborder: CWLObjectType = {
        "inp": {
            "class": "File",
            "location": get_data("tests/wf/whale.txt"),
        }
    }

    job = next(clt.job(joborder, None, runtime_context))
    assert isinstance(job, JobBase)

    job._setup(runtime_context)


streaming = [
    (True, True, False),
    (True, False, True),
    (False, True, True),
    (False, False, True),
]


@pytest.mark.parametrize("streamable,streaming_allowed,raise_exception", streaming)
def test_input_can_be_named_pipe(
    tmp_path: Path, streamable: bool, streaming_allowed: bool, raise_exception: bool
) -> None:
    """Test that input can be a named pipe."""
    clt = CommandLineTool(
        toolpath_object,
        loading_context,
    )

    runtime_context = RuntimeContext()
    runtime_context.streaming_allowed = streaming_allowed

    path = tmp_path / "tmp"
    os.mkfifo(path)

    joborder: CWLObjectType = {
        "inp": {
            "class": "File",
            "location": str(path),
            "streamable": streamable,
        }
    }

    job = next(clt.job(joborder, None, runtime_context))
    assert isinstance(job, JobBase)

    if raise_exception:
        with pytest.raises(WorkflowException):
            job._setup(runtime_context)
    else:
        job._setup(runtime_context)
