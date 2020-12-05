from typing import Any

from cwltool.context import RuntimeContext
from cwltool.docker import DockerCommandLineJob
from cwltool.pathmapper import PathMapper
from .util import get_empty_builder


def test_docker_append_volume_read_only(mocker: Any) -> None:
    mocker.patch("os.mkdir")
    runtime = ["runtime"]
    characters = ":,\"'"
    builder = get_empty_builder(RuntimeContext())
    docker_job = DockerCommandLineJob(builder, {}, PathMapper, [], [], "")
    docker_job.append_volume(runtime, "/source" + characters, "/target" + characters)
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
    builder = get_empty_builder(RuntimeContext())
    docker_job = DockerCommandLineJob(builder, {}, PathMapper, [], [], "")
    docker_job.append_volume(
        runtime, "/source" + characters, "/target" + characters, True
    )
    assert runtime == [
        "runtime",
        "--mount=type=bind," '"source=/source:,""\'",' '"target=/target:,""\'"',
    ]
