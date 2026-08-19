"""Tests --validation."""

import io
import logging
import re

import pytest

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


def test_validate_warns_on_format_for_non_file() -> None:
    """`format` on a non-File parameter (e.g. Directory) warns but still validates (#1616, #607)."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-directory.cwl")],
        logger_handler=handler,
    )
    log_text = re.sub(r"\s\s+", " ", custom_log.getvalue())
    assert exit_code == 0
    assert "'format' is only valid for 'File' type parameters" in log_text
    assert "'indir' is not a File" in log_text


def test_validate_no_format_warning_for_file() -> None:
    """`format` on a File parameter is valid and must not warn (#1616, #607)."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-file.cwl")],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "'format' is only valid" not in custom_log.getvalue()


def test_validate_no_format_warning_for_file_array() -> None:
    """`format` on File[] is valid; covers array type with string items."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-file-array.cwl")],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "'format' is only valid" not in custom_log.getvalue()


def test_validate_warns_on_format_for_directory_array() -> None:
    """`format` on Directory[] warns; covers array type recursion."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-directory-array.cwl")],
        logger_handler=handler,
    )
    log_text = re.sub(r"\s\s+", " ", custom_log.getvalue())
    assert exit_code == 0
    assert "'format' is only valid for 'File' type parameters" in log_text
    assert "'dirs' is not a File" in log_text


def test_validate_no_format_warning_for_record_with_file() -> None:
    """`format` on a record containing a File field must not warn."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-record-file.cwl")],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "'format' is only valid" not in custom_log.getvalue()


def test_validate_warns_on_format_for_record_without_file() -> None:
    """`format` on a record with no File field warns; covers record type recursion."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/format-on-record-string.cwl")],
        logger_handler=handler,
    )
    log_text = re.sub(r"\s\s+", " ", custom_log.getvalue())
    assert exit_code == 0
    assert "'format' is only valid for 'File' type parameters" in log_text
    assert "'rec' is not a File" in log_text


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
    assert "tests/CometAdapter.cwl:10:3: object id" in stdout
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
    assert "tests/CometAdapter.cwl:10:3: object id" not in stdout
    assert "tests/CometAdapter.cwl:10:3: object id" not in stderr
    assert "tests/CometAdapter.cwl:10:3: object id" in custom_log_text
    assert "tests/CometAdapter.cwl#out' previously defined" not in stdout
    assert "tests/CometAdapter.cwl#out' previously defined" not in stderr
    assert "tests/CometAdapter.cwl#out' previously defined" in custom_log_text


def test_validate_warns_on_basecommand_with_space() -> None:
    """A 'baseCommand' string containing whitespace warns but still validates."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, stdout, stderr = get_main_output(
        ["--validate", get_data("tests/wf/2240-basecommand-space.cwl")],
        logger_handler=handler,
    )
    custom_log_text = re.sub(r"\s\s+", " ", custom_log.getvalue())
    assert exit_code == 0
    assert "is valid CWL" in stdout
    assert "'baseCommand' is a single string containing whitespace" in custom_log_text
    assert "'tar xf'" in custom_log_text
    assert "['tar', 'xf']" in custom_log_text


@pytest.mark.parametrize(
    "cwl_file",
    ["tests/wf/2240-basecommand-list.cwl", "tests/CometAdapter.cwl"],
)
def test_validate_no_basecommand_space_warning(cwl_file: str) -> None:
    """A list-form (or absent) 'baseCommand' does not trigger the whitespace warning."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data(cwl_file)],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "single string containing whitespace" not in custom_log.getvalue()


def test_validate_warns_when_base_command_not_on_path() -> None:
    """A 'baseCommand' that is not on the PATH warns but still validates."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, stdout, stderr = get_main_output(
        ["--validate", get_data("tests/wf/2240-basecommand-unavailable.cwl")],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "is valid CWL" in stdout
    assert "cannot find 'definitely_not_a_real_command_xyz' on the PATH" in custom_log.getvalue()


def test_validate_warns_when_list_base_command_not_on_path() -> None:
    """A list-form 'baseCommand' whose program is missing warns but validates."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data("tests/wf/2240-basecommand-list-missing.cwl")],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "cannot find 'definitely_not_a_real_command_xyz' on the PATH" in custom_log.getvalue()


@pytest.mark.parametrize(
    "cwl_file",
    ["tests/wf/2240-basecommand-available.cwl", "tests/wf/2240-basecommand-path.cwl"],
)
def test_validate_no_missing_basecommand_warning(cwl_file: str) -> None:
    """A 'baseCommand' that resolves on the PATH (or is an absolute path) does not warn."""
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    exit_code, _, _ = get_main_output(
        ["--validate", get_data(cwl_file)],
        logger_handler=handler,
    )
    assert exit_code == 0
    assert "cannot find" not in custom_log.getvalue()


def test_container_has_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """_container_has_command probes an image only when it is present locally."""
    import cwltool.command_line_tool as clt

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 1

        result = Result()
        if cmd[1] == "image":
            result.returncode = 1
        return result

    monkeypatch.setattr(clt.subprocess, "run", fake_run)
    assert clt._container_has_command("docker", "missing:latest", "foo") is None
    assert calls[-1][1] == "image"

    def fake_run2(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0 if cmd[1] == "image" or "true" in cmd else 1

        result = Result()
        return result

    monkeypatch.setattr(clt.subprocess, "run", fake_run2)
    assert clt._container_has_command("docker", "present:latest", "foo") is False
    assert "sh" in calls[-2] and "foo" in calls[-2]

    def fake_run3(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0 if cmd[1] == "image" else 1

        result = Result()
        if cmd[1] == "run" and "true" in cmd:
            result.returncode = 1
        return result

    monkeypatch.setattr(clt.subprocess, "run", fake_run3)
    assert clt._container_has_command("docker", "distroless:latest", "foo") is None

    def fake_run4(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0

        result = Result()
        return result

    monkeypatch.setattr(clt.subprocess, "run", fake_run4)
    assert clt._container_has_command("docker", "full:latest", "foo") is True


def test_validate_warns_for_missing_basecommand_in_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: str
) -> None:
    """A base command missing from a locally available image warns but validates."""
    import cwltool.command_line_tool as clt

    monkeypatch.setattr(
        clt,
        "_container_has_command",
        lambda docker, image, command: False,
    )
    monkeypatch.setattr(clt.shutil, "which", lambda exe: "docker")
    custom_log = io.StringIO()
    handler = logging.StreamHandler(custom_log)
    handler.setLevel(logging.DEBUG)
    with open(get_data("tests/wf/2240-basecommand-unavailable.cwl"), encoding="utf-8") as f:
        tool = f.read()
    tool = tool.replace(
        "inputs: []",
        "requirements:\n  - class: DockerRequirement\n    dockerPull: ubuntu:latest\ninputs: []",
    )
    tool_file = tmp_path / "2240-basecommand-in-container.cwl"
    tool_file.write_text(tool, encoding="utf-8")
    exit_code, _, _ = get_main_output(["--validate", str(tool_file)], logger_handler=handler)
    assert exit_code == 0
    assert (
        "cannot find 'definitely_not_a_real_command_xyz' inside container image 'ubuntu:latest'"
        in custom_log.getvalue()
    )
