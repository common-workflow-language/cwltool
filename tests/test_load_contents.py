"""Test the loadContents feature."""

import json
from pathlib import Path
from unittest.mock import patch

from cwltool.builder import content_limit_respected_read
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


def test_load_contents_file_array_for_step_input(tmp_path: Path) -> None:
    """Ensures that a File[] in a step input with loadContents loads each file."""
    params = [
        "--outdir",
        str(tmp_path),
        get_data("tests/load_contents-array-step-input.cwl"),
    ]

    with patch(
        "cwltool.workflow_job.content_limit_respected_read", wraps=content_limit_respected_read
    ) as mock_read:
        assert main(params) == 0
        assert mock_read.call_count == 2  # Exactly 2 files should be read

    with open(tmp_path / "data.json") as out_fd:
        data = json.load(out_fd)
    assert data == {"data": [1, 2]}


def test_load_contents_file_array_for_step_input_with_preloaded_contents(tmp_path: Path) -> None:
    """Ensures that loadContents skips re-reading files whose contents are already set."""
    params = [
        "--outdir",
        str(tmp_path),
        get_data("tests/load_contents-array-step-input-preloaded.cwl"),
        get_data("tests/load_contents-array-step-input-preloaded.yml"),
    ]

    with patch(
        "cwltool.workflow_job.content_limit_respected_read", wraps=content_limit_respected_read
    ) as mock_read:
        assert main(params) == 0
        mock_read.assert_not_called()  # Should not read from disk when contents already present

    with open(tmp_path / "data.json") as out_fd:
        data = json.load(out_fd)
    assert data == {"data": [1, 2]}
