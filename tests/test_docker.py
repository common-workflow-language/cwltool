"""Tests for docker engine."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from cwltool.docker import docker_is_podman
from cwltool.main import main

from .util import (
    get_data,
    get_main_output,
    needs_docker,
    needs_podman,
    needs_singularity,
)


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


@needs_docker
def test_docker_iwdr() -> None:
    result_code = main(
        [
            "--default-container",
            "docker.io/debian:stable-slim",
            "--debug",
            get_data("tests/wf/iwdr-entry.cwl"),
            "--message",
            "hello",
        ]
    )
    assert result_code == 0


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


@needs_docker
def test_docker_required_secfile(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--outdir",
            str(tmp_path),
            get_data("tests/secondary-files-required-container.cwl"),
        ]
    )
    assert result_code == 0, stderr
    assert (
        json.loads(stdout)["output"]["secondaryFiles"][0]["checksum"]
        == "sha1$da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )


@needs_podman
def test_podman_required_secfile(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--podman",
            "--outdir",
            str(tmp_path),
            get_data("tests/secondary-files-required-container.cwl"),
        ]
    )
    assert result_code == 0, stderr
    assert (
        json.loads(stdout)["output"]["secondaryFiles"][0]["checksum"]
        == "sha1$da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )


def test_docker_is_podman(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_fnf(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "check_output", raise_fnf)
    assert docker_is_podman.__wrapped__() is False

    def raise_cpe(*args: Any, **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(returncode=1, cmd="docker")

    monkeypatch.setattr(subprocess, "check_output", raise_cpe)
    assert docker_is_podman.__wrapped__() is False

    def return_docker(*args: Any, **kwargs: Any) -> str:
        return " A self-sufficient runtime for containers"

    monkeypatch.setattr(subprocess, "check_output", return_docker)
    assert docker_is_podman.__wrapped__() is False

    def return_podman(*args: Any, **kwargs: Any) -> str:
        return "Emulate Docker CLI using podman. Create /etc/containers/nodocker to quiet msg."

    monkeypatch.setattr(subprocess, "check_output", return_podman)
    assert docker_is_podman.__wrapped__() is True


@needs_singularity
def test_singularity_required_secfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    singularity_dir = tmp_path / "singularity"
    singularity_dir.mkdir()
    with monkeypatch.context() as m:
        m.setenv("CWL_SINGULARITY_CACHE", str(singularity_dir))
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                "--outdir",
                str(tmp_path / "out"),
                get_data("tests/secondary-files-required-container.cwl"),
            ]
        )
        assert result_code == 0, stderr
        assert (
            json.loads(stdout)["output"]["secondaryFiles"][0]["checksum"]
            == "sha1$da39a3ee5e6b4b0d3255bfef95601890afd80709"
        )


@needs_docker
def test_docker_required_missing_secfile(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--outdir",
            str(tmp_path),
            get_data("tests/secondary-files-required-missing-container.cwl"),
        ]
    )
    assert result_code == 1, stderr
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Job error:" in stderr
    assert "Error collecting output for parameter 'output'" in stderr
    assert (
        "tests/secondary-files-required-missing-container.cwl:16:5: Missing required secondary file"
    ) in stderr
    assert "file.ext3" in stderr


@needs_podman
def test_podman_required_missing_secfile(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--podman",
            "--outdir",
            str(tmp_path),
            get_data("tests/secondary-files-required-missing-container.cwl"),
        ]
    )
    assert result_code == 1, stderr
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Job error:" in stderr
    assert "Error collecting output for parameter 'output'" in stderr
    assert (
        "tests/secondary-files-required-missing-container.cwl:16:5: Missing required secondary file"
    ) in stderr
    assert "file.ext3" in stderr


@needs_singularity
def test_singularity_required_missing_secfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    singularity_dir = tmp_path / "singularity"
    singularity_dir.mkdir()
    with monkeypatch.context() as m:
        m.setenv("CWL_SINGULARITY_CACHE", str(singularity_dir))
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                "--outdir",
                str(tmp_path),
                get_data("tests/secondary-files-required-missing-container.cwl"),
            ]
        )
        assert result_code == 1, stderr
        stderr = re.sub(r"\s\s+", " ", stderr)
        assert "Job error:" in stderr
        assert "Error collecting output for parameter 'output'" in stderr
        assert (
            "tests/secondary-files-required-missing-container.cwl:16:5: Missing required secondary file"
            in stderr
        )
        assert "file.ext3" in stderr


@needs_docker
def test_docker_shm_size(tmp_path: Path) -> None:
    result_code, stdout, stderr = get_main_output(
        [
            "--enable-ext",
            "--default-container",
            "docker.io/debian:stable-slim",
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/shm_size.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert result_code == 0
    assert "--shm-size=128m" in stderr
