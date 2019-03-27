from __future__ import absolute_import

import os
import shutil
import tempfile
import sys
import re
from io import StringIO

import pytest

from cwltool.main import main


from .util import get_data, needs_docker, temp_dir, windows_needs_docker

#FIXME needs mocking

@needs_docker
def test_tool_trs_template():
    params = ["--make-template", "quay.io/briandoconnor/dockstore-tool-md5sum:1.0.4"]
    assert main(params) == 0

@needs_docker
def test_workflow_trs_template():
    params = ["--make-template", '#workflow/github.com/dockstore-testing/md5sum-checker:develop']
    assert main(params) == 0
