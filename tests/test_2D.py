from pathlib import Path

from .util import get_data, get_main_output


def test_output_2d_file_format(tmp_path: Path) -> None:
    """A simple test for format tag fix for 2D output arrays."""

    # still need to create 'filename.txt' as it is needed in output_2D_file_format.cwl
    (tmp_path / "filename.txt").touch()
    commands = [
        "--cachedir",
        str(tmp_path / "foo"),  # just so that the relative path of file works out
        "--outdir",
        str(tmp_path / "out"),
        get_data("tests/output_2D_file_format.cwl"),
    ]

    error_code, _, stderr = get_main_output(commands)

    assert error_code == 0, stderr
