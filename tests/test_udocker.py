import pytest
import os
import subprocess

from .util import get_data, get_main_output
from psutil import LINUX


@pytest.mark.skipIf(not LINUX, "LINUX only")
def test_udocker_usage_should_not_write_cid_file(tmpdir):
    cwd = tmpdir.chdir()
    install_cmds = [
        "curl https://raw.githubusercontent.com/indigo-dc/udocker/master/udocker.py -o ./udocker",
        "chmod u+rx ./udocker",
        "./udocker install"]
    os.environ['UDOCKER_DIR'] = os.path.join(str(tmpdir), ".udocker")

    assert sum([subprocess.call(cmd.split()) for cmd in install_cmds]) == 0

    docker_path = os.path.join(str(tmpdir), 'udocker')

    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    error_code, stdout, stderr = get_main_output(
        ["--debug", "--default-container", "debian", "--user-space-docker-cmd=" + docker_path,
         get_data(test_file), get_data(job_file)])
    cwd.chdir()
    cidfiles_count = sum(1 for _ in tmpdir.visit(fil="*.cid"))

    tmpdir.remove(ignore_errors=True)

    assert "completed success" in stderr
    assert cidfiles_count == 0
