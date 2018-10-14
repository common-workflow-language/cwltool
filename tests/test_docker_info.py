import pytest
from .util import get_data, get_main_output, needs_docker

@needs_docker
def test_docker_mem():
    error_code, stdout, stderr = get_main_output(
        ["--default-container=debian", "--enable-ext",
         get_data("tests/wf/timelimit.cwl"), "--sleep_time", "10"])
    assert "Max memory used" in stderr, stderr
