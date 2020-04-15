import subprocess

from cwltool.context import RuntimeContext
from tests.util import get_windows_safe_factory, get_data


def test_replace_default_stdout_stderr():
    import sys
    # break stdout & stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = ''
    sys.stderr = ''

    runtime_context = RuntimeContext()
    runtime_context.default_stdout = subprocess.DEVNULL
    runtime_context.default_stderr = subprocess.DEVNULL
    factory = get_windows_safe_factory(runtime_context=runtime_context)
    echo = factory.make(get_data("tests/echo.cwl"))

    assert echo(inp="foo") == {"out": "foo\n"}
    sys.stdout = original_stdout
    sys.stderr = original_stderr
