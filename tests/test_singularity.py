"""Tests to find local Singularity image."""
import shutil
from pathlib import Path
from typing import Any

from cwltool.main import main

from .util import (
    get_data,
    get_main_output,
    needs_singularity,
    needs_singularity_2_6,
    needs_singularity_3_or_newer,
    working_directory,
)


@needs_singularity_2_6
def test_singularity_pullfolder(tmp_path: Path, monkeypatch: Any) -> None:
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


def test_singularity_iwdr() -> None:
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
