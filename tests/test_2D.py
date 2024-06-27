import subprocess
import sys
from pathlib import Path

from .util import get_data


def test_output_2D_file_format() -> None:
    """A simple test for format tag fix for 2D output arrays."""

    Path("filename.txt").touch()
    params = [
        sys.executable,
        "-m",
        "cwltool",
        "--cachedir",  # just so that the relative path of file works out
        "foo",
        get_data("tests/output_2D_file_format.cwl"),
    ]

    assert subprocess.check_call(params) == 0
