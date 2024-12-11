"""Tests --validation."""

import io
import logging
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
    stdout = re.sub(r"\s\s+", " ", stdout)
    assert "Invalid job input record" in stdout
    assert (
        "tests/wf/1st-workflow_bad_inputs.yml:2:1: * the 'ex' field is not "
        "valid because the value is not string" in stdout
    )
    assert (
        "tests/wf/1st-workflow_bad_inputs.yml:1:1: * the 'inp' field is not "
        "valid because is not a dict. Expected a File object." in stdout
    )


def test_validate_quiet() -> None:
    """Ensure that --validate --quiet prints the correct amount of information."""
    exit_code, stdout, stderr = get_main_output(
        [
            "--validate",
            "--quiet",
            get_data("tests/CometAdapter.cwl"),
        ]
    )
    assert exit_code == 0
    stdout = re.sub(r"\s\s+", " ", stdout)
    assert "INFO" not in stdout
    assert "INFO" not in stderr
    assert "tests/CometAdapter.cwl:9:3: object id" in stdout
    assert "tests/CometAdapter.cwl#out' previously defined" in stdout


def test_validate_no_warnings() -> None:
    """Ensure that --validate --no-warnings doesn't print any warnings."""
    exit_code, stdout, stderr = get_main_output(
        [
            "--validate",
            "--no-warnings",
            get_data("tests/CometAdapter.cwl"),
        ]
    )
    assert exit_code == 0
    stdout = re.sub(r"\s\s+", " ", stdout)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "INFO" not in stdout
    assert "INFO" not in stderr
    assert "WARNING" not in stdout
    assert "WARNING" not in stderr
    assert "tests/CometAdapter.cwl:9:3: object id" not in stdout
    assert "tests/CometAdapter.cwl:9:3: object id" not in stderr
    assert "tests/CometAdapter.cwl#out' previously defined" not in stdout
    assert "tests/CometAdapter.cwl#out' previously defined" not in stderr


def test_validate_custom_logger() -> None:
    """Custom log handling test."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, stdout, stderr = get_main_output(
        [
            "--validate",
            get_data("tests/CometAdapter.cwl"),
        ],
        logger_handler=handler,
    )
    custom_log_text = custom_log.getvalue()
    assert exit_code == 0
    custom_log_text = re.sub(r"\s\s+", " ", custom_log_text)
    stdout = re.sub(r"\s\s+", " ", stdout)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "INFO" not in stdout
    assert "INFO" not in stderr
    assert "INFO" in custom_log_text
    assert "WARNING" not in stdout
    assert "WARNING" not in stderr
    assert "WARNING" in custom_log_text
    assert "tests/CometAdapter.cwl:9:3: object id" not in stdout
    assert "tests/CometAdapter.cwl:9:3: object id" not in stderr
    assert "tests/CometAdapter.cwl:9:3: object id" in custom_log_text
    assert "tests/CometAdapter.cwl#out' previously defined" not in stdout
    assert "tests/CometAdapter.cwl#out' previously defined" not in stderr
    assert "tests/CometAdapter.cwl#out' previously defined" in custom_log_text
