import json
import logging
import os
import shutil
import sys
from io import BytesIO, StringIO
import pytest

import schema_salad.validate

import cwltool.checker
import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from cwltool.context import RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.main import main
from cwltool.utils import onWindows

from .util import (get_data, get_main_output, get_windows_safe_factory, needs_docker,
                   needs_singularity, temp_dir, windows_needs_docker)

sys.argv = ['']


@needs_singularity
def test_singularity_workflow():
    error_code, _, stderr = get_main_output(
        ['--singularity', '--default-container', 'debian',
         get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert "completed success" in stderr
    assert error_code == 0

@needs_singularity
def test_singularity_iwdr():
    result = main(
        ['--singularity', '--default-container', 'debian',
         get_data("tests/wf/iwdr-entry.cwl"), "--message", "hello"])
    assert result == 0
