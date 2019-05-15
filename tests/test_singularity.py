import sys
import os
import pytest

import distutils.spawn

import schema_salad.validate

from cwltool.main import main

from .util import (get_data, get_main_output, needs_singularity,
                   working_directory)

sys.argv = ['']


@needs_singularity
def test_singularity_pullfolder(tmp_path):

    if "SINGULARITY_PULLFOLDER" in os.environ:
        del os.environ["SINGULARITY_PULLFOLDER"]
        workdir = tmp_path / "working_dir_new"
        workdir.mkdir()
        os.chdir(str(workdir))
        pullfolder = tmp_path / "pull_folder"
        pullfolder.mkdir()
        os.environ["SINGULARITY_PULLFOLDER"] = str(pullfolder)
        if "SINGULARITY_PULLFOLDER" in os.environ:
            result_code, stdout, stderr = get_main_output(
                ['--singularity', get_data("tests/sing_pullfolder_test.cwl"), "--message", "hello"])
            assert result_code == 0
        else:
            assert result_code != 0
    else:
        workdir = tmp_path / "working_dir_new"
        workdir.mkdir()
        os.chdir(str(workdir))
        pullfolder = tmp_path / "pullfolder"
        pullfolder.mkdir()
        os.environ["SINGULARITY_PULLFOLDER"] = str(pullfolder)
        if "SINGULARITY_PULLFOLDER" in os.environ:
            result_code, stdout, stderr = get_main_output(
                ['--singularity', get_data("tests/sing_pullfolder_test.cwl"), "--message", "hello"])
            assert result_code == 0
        else:
            assert result_code != 0

@needs_singularity
def test_singularity_workflow(tmpdir):
    with working_directory(str(tmpdir)):
        error_code, _, stderr = get_main_output(
            ['--singularity', '--default-container', 'debian', '--debug',
             get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert "completed success" in stderr, stderr
    assert error_code == 0

def test_singularity_iwdr():
    result_code = main(
        ['--singularity', '--default-container', 'debian',
         get_data("tests/wf/iwdr-entry.cwl"), "--message", "hello"])
    singularity_installed = bool(distutils.spawn.find_executable('singularity'))
    if singularity_installed:
        assert result_code == 0
    else:
        assert result_code != 0

@needs_singularity
def test_singularity_incorrect_image_pull():
    result_code, _, stderr = get_main_output(
        ['--singularity', '--default-container', 'non-existant-weird-image',
         get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert result_code != 0

@needs_singularity
def test_singularity_local(tmp_path):
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    os.chdir(str(workdir))
    result_code, stdout, stderr = get_main_output(
        ['--singularity', get_data("tests/sing_pullfolder_test.cwl"), "--message", "hello"])
    assert result_code == 0

@needs_singularity
def test_singularity_docker_image_id_in_tool():
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    os.chdir(str(workdir))
    result_code, stdout, stderr = get_main_output(
        ['--singularity', get_data("tests/sing_pullfolder_test.cwl"), "--message", "hello"])
    result_code1, stdout, stderr = get_main_output(
        ['--singularity', get_data("tests/debian_image_id.cwl"), "--message", "hello"])
    assert result_code1 == 0
