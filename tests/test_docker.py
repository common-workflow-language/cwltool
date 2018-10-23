import pytest

from distutils import spawn

from cwltool.docker import DockerCommandLineJob
from cwltool.main import main

from .util import get_data, get_main_output, needs_docker, needs_singularity

@needs_docker
def test_docker_workflow():
    result_code, _, stderr = get_main_output(
        ['--default-container', 'debian',
         get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert "completed success" in stderr
    assert result_code == 0

def test_docker_iwdr():
    result_code = main(
        ['--default-container', 'debian',
         get_data("tests/wf/iwdr-entry.cwl"), "--message", "hello"])
    docker_installed = bool(spawn.find_executable('docker'))
    if docker_installed:
        assert result_code == 0
    else:
        assert result_code != 0

@needs_docker
def test_docker_incorrect_image_pull():
    result_code = main(
        ['--default-container', 'non-existant-weird-image',
         get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert result_code != 0
