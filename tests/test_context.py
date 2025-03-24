import subprocess
import sys
import logging
from io import StringIO
from typing import MutableMapping, cast

from cwltool.context import RuntimeContext
from cwltool.factory import Factory
from cwltool.utils import CWLObjectType, CWLOutputType
from cwltool.workflow_job import WorkflowJobStep

from .util import get_data


def test_replace_default_stdout_stderr() -> None:
    """Test our ability to replace the default stdout/err."""

    # break stdout & stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = ""
    sys.stderr = ""

    runtime_context = RuntimeContext()
    runtime_context.default_stdout = subprocess.DEVNULL  # type: ignore
    runtime_context.default_stderr = subprocess.DEVNULL  # type: ignore
    factory = Factory(None, None, runtime_context)
    echo = factory.make(get_data("tests/echo.cwl"))

    assert echo(inp="foo") == {"out": "foo\n"}
    sys.stdout = original_stdout
    sys.stderr = original_stderr


def test_workflow_job_step_name_callback() -> None:
    """Test ability to hook custom workflow step naming"""

    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    try:
        runtime_context = RuntimeContext()

        def step_name_hook(step: WorkflowJobStep, job: CWLObjectType) -> str:
            j1 = cast(MutableMapping[str, CWLObjectType], job)
            inp = cast(MutableMapping[str, str], j1.get("revtool_input", j1.get("sorted_input")))
            return "%s on %s" % (
                step.name,
                inp.get("basename"),
            )

        runtime_context.workflow_job_step_name_callback = step_name_hook

        factory = Factory(None, None, runtime_context)
        revsort = factory.make(get_data("tests/wf/revsort.cwl"))

        result = revsort(
            workflow_input={
                "class": "File",
                "location": "whale.txt",
                "format": "https://www.iana.org/assignments/media-types/text/plain",
            }
        )

        result = cast(CWLObjectType, result)

        sorted_out = cast(MutableMapping[str, str], result["sorted_output"])
        loc = sorted_out["location"]

        assert result == {
            "sorted_output": {
                "basename": "output.txt ",
                "checksum": "sha1$b9214658cc453331b62c2282b772a5c063dbd284",
                "class": "File",
                "http://commonwl.org/cwltool#generation": 0,
                "nameext": ".txt",
                "nameroot": "output",
                "size": 1111,
                "location": loc,
            },
        }

        print(stream.getvalue())

        assert "foostep" in stream.getvalue()
    finally:
        _logger.removeHandler(streamhandler)
