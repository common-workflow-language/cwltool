from distutils import spawn

import pytest

from cwltool.docker import DockerCommandLineJob
from cwltool.main import main

from .util import get_data, get_main_output, needs_docker, needs_singularity


@needs_docker
def test_docker_workflow(tmpdir):
    result_code, _, stderr = get_main_output(
        [
            "--default-container",
            "debian",
            "--outdir",
            str(tmpdir),
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "hello",
        ]
    )
    assert "completed success" in stderr
    assert result_code == 0


def test_docker_iwdr():
    result_code = main(
        [
            "--default-container",
            "debian",
            get_data("tests/wf/iwdr-entry.cwl"),
            "--message",
            "hello",
        ]
    )
    docker_installed = bool(spawn.find_executable("docker"))
    if docker_installed:
        assert result_code == 0
    else:
        assert result_code != 0


@needs_docker
def test_docker_incorrect_image_pull():
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
def test_docker_file_mount():
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
