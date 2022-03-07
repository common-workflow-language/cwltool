"""Tests for docker engine."""
import re
from pathlib import Path
from shutil import which

from cwltool.main import main

from .util import get_data, get_main_output, needs_docker


@needs_docker
def test_docker_workflow(tmp_path: Path) -> None:
    """Basic test for docker with a CWL Workflow."""
    result_code, _, stderr = get_main_output(
        [
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "hello",
        ]
    )
    assert "completed success" in stderr
    assert (tmp_path / "response.txt").read_text("utf-8") == "hello"
    assert result_code == 0


def test_docker_iwdr() -> None:
    result_code = main(
        [
            "--default-container",
            "docker.io/debian:stable-slim",
            get_data("tests/wf/iwdr-entry.cwl"),
            "--message",
            "hello",
        ]
    )
    docker_installed = bool(which("docker"))
    if docker_installed:
        assert result_code == 0
    else:
        assert result_code != 0


@needs_docker
def test_docker_incorrect_image_pull() -> None:
    result_code = main(
        [
            "--default-container",
            "non-existant-weird-image",
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "hello",
        ]
    )
    assert result_code != 0


@needs_docker
def test_docker_file_mount() -> None:
    # test for bug in
    # ContainerCommandLineJob.create_file_and_add_volume()
    #
    # the bug was that it would use the file literal contents as the
    # temporary file name, which can easily result in a file name that
    # is too long or otherwise invalid.  This test case uses ".."
    result_code = main(
        [get_data("tests/wf/literalfile.cwl"), get_data("tests/wf/literalfile-job.yml")]
    )
    assert result_code == 0


@needs_docker
def test_docker_strict_cpu_limit(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--strict-cpu-limit",
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/cores_float.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert result_code == 0
    assert "--cpus=2" in stderr


@needs_docker
def test_docker_strict_memory_limit(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--strict-memory-limit",
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/storage_float.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert result_code == 0
    assert "--memory=255m" in stderr


@needs_docker
def test_docker_strict_cpu_limit_warning(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/cores_float.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert result_code == 0
    assert "Skipping Docker software container '--cpus' limit" in stderr


@needs_docker
def test_docker_strict_memory_limit_warning(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/storage_float.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert result_code == 0
    assert "Skipping Docker software container '--memory' limit" in stderr
