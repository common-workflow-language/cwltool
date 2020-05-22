from cwltool.docker import DockerCommandLineJob
from cwltool.main import main

from .util import needs_docker

from typing import Any

def test_docker_append_volume_read_only(mocker: Any) -> None:
    mocker.patch("os.mkdir")
    runtime = ["runtime"]
    characters = ":,\"'"
    DockerCommandLineJob.append_volume(
        runtime, "/source" + characters, "/target" + characters
    )
    assert runtime == [
        "runtime",
        "--mount=type=bind,"
        '"source=/source:,""\'",'
        '"target=/target:,""\'",'
        "readonly",
    ]


def test_docker_append_volume_read_write(mocker: Any) -> None:
    mocker.patch("os.mkdir")
    runtime = ["runtime"]
    characters = ":,\"'"
    DockerCommandLineJob.append_volume(
        runtime, "/source" + characters, "/target" + characters, True
    )
    assert runtime == [
        "runtime",
        "--mount=type=bind," '"source=/source:,""\'",' '"target=/target:,""\'"',
    ]
