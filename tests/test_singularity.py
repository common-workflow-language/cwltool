"""Tests to find local Singularity image."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cwltool.main import main
from cwltool.singularity import _inspect_singularity_image

from .util import (
    get_data,
    get_main_output,
    needs_singularity,
    needs_singularity_2_6,
    needs_singularity_3_or_newer,
    working_directory,
)


@needs_singularity_2_6
def test_singularity_pullfolder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test singularity respects SINGULARITY_PULLFOLDER."""
    workdir = tmp_path / "working_dir_new"
    workdir.mkdir()
    with working_directory(workdir):
        pullfolder = tmp_path / "pullfolder"
        pullfolder.mkdir()
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ],
            extra_env={"SINGULARITY_PULLFOLDER": str(pullfolder)},
            monkeypatch=monkeypatch,
        )
        print(stdout)
        print(stderr)
        assert result_code == 0
        image = pullfolder / "debian.img"
        assert image.exists()


@needs_singularity
def test_singularity_workflow(tmp_path: Path) -> None:
    with working_directory(tmp_path):
        error_code, _, stderr = get_main_output(
            [
                "--singularity",
                "--default-container",
                "docker.io/debian:stable-slim",
                "--debug",
                get_data("tests/wf/hello-workflow.cwl"),
                "--usermessage",
                "hello",
            ]
        )
    assert "completed success" in stderr, stderr
    assert error_code == 0


def test_singularity_iwdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    singularity_dir = tmp_path / "singularity"
    singularity_dir.mkdir()
    monkeypatch.setenv("CWL_SINGULARITY_CACHE", str(singularity_dir))
    result_code = main(
        [
            "--singularity",
            "--default-container",
            "docker.io/debian:stable-slim",
            get_data("tests/wf/iwdr-entry.cwl"),
            "--message",
            "hello",
        ]
    )
    singularity_installed = bool(shutil.which("singularity"))
    if singularity_installed:
        assert result_code == 0
    else:
        assert result_code != 0


@needs_singularity
def test_singularity_incorrect_image_pull() -> None:
    result_code, _, stderr = get_main_output(
        [
            "--singularity",
            "--default-container",
            "non-existant-weird-image",
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "hello",
        ]
    )
    assert result_code != 0


@needs_singularity
def test_singularity_local(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0


@needs_singularity_2_6
def test_singularity2_docker_image_id_in_tool(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        result_code1, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/debian_image_id.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code1 == 0


@needs_singularity_3_or_newer
def test_singularity3_docker_image_id_in_tool(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0
        result_code1, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/debian_image_id2.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code1 == 0


@needs_singularity
def test_singularity_local_sandbox_image(tmp_path: Path):
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        # build a sandbox image
        container_path = workdir / "container_repo"
        container_path.mkdir()
        cmd = [
            "singularity",
            "build",
            "--sandbox",
            str(container_path / "alpine"),
            "docker://alpine:latest",
        ]

        build = subprocess.run(cmd, capture_output=True, text=True)
        if build.returncode == 0:
            result_code, stdout, stderr = get_main_output(
                [
                    "--singularity",
                    "--disable-pull",
                    get_data("tests/sing_local_sandbox_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0
            result_code, stdout, stderr = get_main_output(
                [
                    "--singularity",
                    "--disable-pull",
                    get_data("tests/sing_local_sandbox_img_id_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0
        else:
            pytest.skip(f"Failed to build the singularity image: {build.stderr}")


@needs_singularity
def test_singularity_inspect_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test inspect a real image works."""
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    repo_path = workdir / "container_repo"
    image_path = repo_path / "alpine"

    # test image exists
    repo_path.mkdir()
    cmd = [
        "singularity",
        "build",
        "--sandbox",
        str(image_path),
        "docker://alpine:latest",
    ]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode == 0:
        # Verify the path is a correct container image
        res_inspect = _inspect_singularity_image(str(image_path))
        assert res_inspect is True
    else:
        pytest.skip(f"singularity sandbox image build didn't worked: {build.stderr}")


def _make_run_result(returncode: int, stdout: str):
    """Mock subprocess.run returning returncode and stdout."""

    class DummyResult:  # noqa: B903
        def __init__(self, rc, out):
            self.returncode = rc
            self.stdout = out

    def _runner(*args, **kwargs):
        return DummyResult(returncode, stdout)

    return _runner


def test_json_decode_error_branch(monkeypatch):
    """Test json can't decode inspect result."""
    monkeypatch.setattr("cwltool.singularity.run", _make_run_result(0, "not-a-json"))

    def _raise_json_error(s):
        # construct and raise an actual JSONDecodeError
        raise json.JSONDecodeError("Expecting value", s, 0)

    monkeypatch.setattr("json.loads", _raise_json_error)

    assert _inspect_singularity_image("/tmp/image") is False


def test_singularity_sandbox_image_not_exists():
    image_path = "/tmp/not_existing/image"
    res_inspect = _inspect_singularity_image(image_path)
    assert res_inspect is False


def test_singularity_sandbox_not_an_image(tmp_path: Path):
    image_path = tmp_path / "image"
    image_path.mkdir()
    res_inspect = _inspect_singularity_image(str(image_path))
    assert res_inspect is False


def test_inspect_image_wrong_sb_call(monkeypatch: pytest.MonkeyPatch):

    def mock_failed_subprocess(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0])

    monkeypatch.setattr("cwltool.singularity.run", mock_failed_subprocess)
    res_inspect = _inspect_singularity_image("/tmp/container_repo/alpine")
    assert res_inspect is False
