"""Test the loadContents feature."""

import json
from pathlib import Path

from cwltool.main import main

from .util import get_data


def test_load_contents_file_array(tmp_path: Path) -> None:
    """Ensures that a File[] input with loadContents loads each file."""
    params = [
        "--outdir",
        str(tmp_path),
        get_data("tests/load_contents-array.cwl"),
        str(Path(__file__) / "../load_contents-array.yml"),
    ]
    assert main(params) == 0
    with open(tmp_path / "data.json") as out_fd:
        data = json.load(out_fd)
    assert data == {"data": [1, 2]}
