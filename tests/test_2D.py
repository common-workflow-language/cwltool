from pathlib import Path
import pytest
from .util import get_data, get_main_output

@pytest.fixture(scope="session")
def test_output_2d_file_format(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A simple test for format tag fix for 2D output arrays."""

    tmp_path: Path = tmp_path_factory.mktemp("tmp")
    # still need to create 'filename.txt' as it is needed in output_2D_file_format.cwl
    _ = tmp_path / "filename.txt"
    commands = [
        "--cachedir",
        str(tmp_path / "foo"),  # just so that the relative path of file works out
        get_data("tests/output_2D_file_format.cwl")]

    error_code, _, stderr = get_main_output(commands)

    assert error_code == 0, stderr
