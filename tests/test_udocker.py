import os
import shutil
import subprocess
import sys
import tempfile

import pytest
from psutil.tests import TRAVIS

from .util import get_data, get_main_output

LINUX = sys.platform in ("linux", "linux2")


# @pytest.mark.skipif(not LINUX, reason="LINUX only")
@pytest.mark.skip(
    "Udocker install is broken, see https://github.com/indigo-dc/udocker/issues/221"
)
class TestUdocker:
    udocker_path = None

    @classmethod
    def setup_class(cls):
        test_cwd = os.getcwd()
        test_environ = os.environ.copy()
        cls.docker_install_dir = tempfile.mkdtemp()
        os.chdir(cls.docker_install_dir)

        url = "https://download.ncg.ingrid.pt/webdav/udocker/udocker-1.1.3.tar.gz"
        install_cmds = [
            ["curl", url, "-o", "./udocker-tarball.tgz"],
            ["tar", "xzvf", "udocker-tarball.tgz", "udocker"],
            [
                "bash",
                "-c",
                "UDOCKER_TARBALL={}/udocker-tarball.tgz ./udocker install".format(
                    cls.docker_install_dir
                ),
            ],
        ]

        os.environ["UDOCKER_DIR"] = os.path.join(cls.docker_install_dir, ".udocker")
        os.environ["HOME"] = cls.docker_install_dir

        results = []
        for _ in range(3):
            results = [subprocess.call(cmds) for cmds in install_cmds]
            if sum(results) == 0:
                break
            subprocess.call(["rm", "./udocker"])

        assert sum(results) == 0

        cls.udocker_path = os.path.join(cls.docker_install_dir, "udocker")
        os.chdir(test_cwd)
        os.environ = test_environ
        print("Udocker install dir: " + cls.docker_install_dir)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.docker_install_dir)

    def test_udocker_usage_should_not_write_cid_file(self, tmpdir):
        cwd = tmpdir.chdir()

        test_file = "tests/wf/wc-tool.cwl"
        job_file = "tests/wf/wc-job.json"
        error_code, stdout, stderr = get_main_output(
            [
                "--debug",
                "--default-container",
                "debian",
                "--user-space-docker-cmd=" + self.udocker_path,
                get_data(test_file),
                get_data(job_file),
            ]
        )
        cwd.chdir()
        cidfiles_count = sum(1 for _ in tmpdir.visit(fil="*.cid"))

        tmpdir.remove(ignore_errors=True)

        assert "completed success" in stderr, stderr
        assert cidfiles_count == 0

    @pytest.mark.skipif(
        TRAVIS, reason="Not reliable on single threaded test on travis."
    )
    def test_udocker_should_display_memory_usage(self, tmpdir):
        cwd = tmpdir.chdir()
        error_code, stdout, stderr = get_main_output(
            [
                "--enable-ext",
                "--default-container=debian",
                "--user-space-docker-cmd=" + self.udocker_path,
                get_data("tests/wf/timelimit.cwl"),
                "--sleep_time",
                "10",
            ]
        )
        cwd.chdir()
        tmpdir.remove(ignore_errors=True)

        assert "completed success" in stderr, stderr
        assert "Max memory" in stderr, stderr
