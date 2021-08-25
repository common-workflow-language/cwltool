import subprocess
import sys

from cwltool.context import RuntimeContext
from cwltool.factory import Factory

from .util import get_data


def test_replace_default_stdout_stderr() -> None:
    """Test our ability to replace the default stdout/err."""

    # break stdout & stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = ""  # type: ignore
    sys.stderr = ""  # type: ignore

    runtime_context = RuntimeContext()
    runtime_context.default_stdout = subprocess.DEVNULL  # type: ignore
    runtime_context.default_stderr = subprocess.DEVNULL  # type: ignore
    factory = Factory(None, None, runtime_context)
    echo = factory.make(get_data("tests/echo.cwl"))

    assert echo(inp="foo") == {"out": "foo\n"}
    sys.stdout = original_stdout
    sys.stderr = original_stderr
