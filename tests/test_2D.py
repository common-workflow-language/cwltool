import subprocess
import sys

from .util import get_data


def test_output_2D_file_format() -> None:
    """Test format tag for 2D output arrays."""

    params = [
        sys.executable,
        "-m",
        "cwltool",
        get_data("tests/output_2D_file_format.cwl"),
    ]

    assert subprocess.check_call(params) == 0
