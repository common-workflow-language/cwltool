"""Tests --validation."""

import re

from .util import get_data, get_main_output


def test_validate_graph_with_no_default() -> None:
    """Ensure that --validate works on $graph docs that lack a main/#main."""
    exit_code, stdout, stderr = get_main_output(
        ["--validate", get_data("tests/wf/packed_no_main.cwl")]
    )
    assert exit_code == 0
    assert "packed_no_main.cwl#echo is valid CWL" in stdout
    assert "packed_no_main.cwl#cat is valid CWL" in stdout
    assert "packed_no_main.cwl#collision is valid CWL" in stdout
    assert "tests/wf/packed_no_main.cwl is valid CWL" in stdout


def test_validate_with_valid_input_object() -> None:
    """Ensure that --validate with a valid input object."""
    exit_code, stdout, stderr = get_main_output(
        [
            "--validate",
            get_data("tests/wf/1st-workflow.cwl"),
            "--inp",
            get_data("tests/wf/1st-workflow.cwl"),
            "--ex",
            "FOO",
        ]
    )
    assert exit_code == 0
    assert "tests/wf/1st-workflow.cwl is valid CWL. No errors detected in the inputs." in stdout


def test_validate_with_invalid_input_object() -> None:
    """Ensure that --validate with an invalid input object."""
    exit_code, stdout, stderr = get_main_output(
        [
            "--validate",
            get_data("tests/wf/1st-workflow.cwl"),
            get_data("tests/wf/1st-workflow_bad_inputs.yml"),
        ]
    )
    assert exit_code == 1
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Invalid job input record" in stderr
    assert (
        "tests/wf/1st-workflow_bad_inputs.yml:2:1: * the 'ex' field is not "
        "valid because the value is not string" in stderr
    )
    assert (
        "tests/wf/1st-workflow_bad_inputs.yml:1:1: * the 'inp' field is not "
        "valid because is not a dict. Expected a File object." in stderr
    )
