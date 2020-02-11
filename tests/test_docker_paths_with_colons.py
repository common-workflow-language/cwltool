import pytest

from cwltool.docker import DockerCommandLineJob
from cwltool.main import main

from .util import needs_docker


def test_docker_append_volume_read_only():
    runtime = ['runtime']
    characters = ':,"\''
    DockerCommandLineJob.append_volume(
        runtime,
        '/source' + characters,
        '/target' + characters
    )
    assert runtime == [
        'runtime',
        '--mount=type=bind,'
        '"source=/source:,""\'",'
        '"target=/target:,""\'",'
        'readonly'
    ]

def test_docker_append_volume_read_write():
    runtime = ['runtime']
    characters = ':,"\''
    DockerCommandLineJob.append_volume(
        runtime,
        '/source' + characters,
        '/target' + characters,
        True
    )
    assert runtime == [
        'runtime',
        '--mount=type=bind,'
        '"source=/source:,""\'",'
        '"target=/target:,""\'"'
    ]
