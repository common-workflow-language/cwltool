import pytest
from .util import get_data, get_main_output

def test_docker_mem():
    error_code, stdout, stderr = get_main_output(
        ["--default-container=debian", "--enable-ext",
         get_data("tests/wf/timelimit.cwl")])
    assert "Max memory used" in stderr, stderr
