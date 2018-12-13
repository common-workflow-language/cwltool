import pytest
import sys
import os
import subprocess
from .util import get_data, get_main_output

LINUX = sys.platform in ('linux', 'linux2')


@pytest.mark.skipif(not LINUX, reason="LINUX only")
class TestUdocker:
    udocker_path = None

    @classmethod
    def setup_class(cls, tmpdir):
        install_cmds = [
            "curl https://raw.githubusercontent.com/indigo-dc/udocker/master/udocker.py -o ./udocker",
            "chmod u+rx ./udocker",
            "./udocker install"]
        os.environ['UDOCKER_DIR'] = os.path.join(str(tmpdir), ".udocker")

        assert sum([subprocess.call(cmd.split()) for cmd in install_cmds]) == 0

        cls.udocker_path = os.path.join(str(tmpdir), 'udocker')

    def test_udocker_usage_should_not_write_cid_file(self, tmpdir):
        cwd = tmpdir.chdir()

        test_file = "tests/wf/wc-tool.cwl"
        job_file = "tests/wf/wc-job.json"
        error_code, stdout, stderr = get_main_output(
            ["--debug", "--default-container", "debian", "--user-space-docker-cmd=" + self.udocker_path,
             get_data(test_file), get_data(job_file)])
        cwd.chdir()
        cidfiles_count = sum(1 for _ in tmpdir.visit(fil="*.cid"))

        tmpdir.remove(ignore_errors=True)

        assert "completed success" in stderr
        assert cidfiles_count == 0

    def test_udocker_should_display_memory_usage(self, tmpdir):
        cwd = tmpdir.chdir()
        tmpdir.remove(ignore_errors=True)
        test_file = "tests/wf/wc-tool.cwl"
        job_file = "tests/wf/wc-job.json"
        error_code, stdout, stderr = get_main_output(
            ["--debug", "--default-container", "debian", "--user-space-docker-cmd=" + self.udocker_path,
             get_data(test_file), get_data(job_file)])
        cwd.chdir()
        tmpdir.remove(ignore_errors=True)

        assert "completed success" in stderr
        assert "Max memory" in stderr
