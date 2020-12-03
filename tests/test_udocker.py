"""Test optional udocker feature."""
import copy
import os
import shutil
import subprocess
import sys

try:
    from psutil.tests import TRAVIS  # type: ignore
except ImportError:
    TRAVIS = True


from pathlib import Path
from typing import Generator

import pytest
from _pytest.tmpdir import TempPathFactory

from .util import get_data, get_main_output

LINUX = sys.platform in ("linux", "linux2")


@pytest.fixture(scope="session")
def udocker(tmp_path_factory: TempPathFactory) -> str:
    """Udocker fixture, returns the path to the udocker script."""
    test_cwd = os.getcwd()
    test_environ = copy.copy(os.environ)
    docker_install_dir = str(tmp_path_factory.mktemp("udocker"))
    os.chdir(docker_install_dir)

    url = "https://raw.githubusercontent.com/jorge-lip/udocker-builds/master/tarballs/udocker-1.1.4.tar.gz"
    install_cmds = [
        ["curl", url, "-o", "./udocker-tarball.tgz"],
        ["tar", "xzvf", "udocker-tarball.tgz", "udocker"],
        [
            "bash",
            "-c",
            "UDOCKER_TARBALL={}/udocker-tarball.tgz ./udocker install".format(
                docker_install_dir
            ),
        ],
    ]

    os.environ["UDOCKER_DIR"] = os.path.join(docker_install_dir, ".udocker")
    os.environ["HOME"] = docker_install_dir

    results = []
    for _ in range(3):
        results = [subprocess.call(cmds) for cmds in install_cmds]
        if sum(results) == 0:
            break
        subprocess.call(["rm", "./udocker"])

    assert sum(results) == 0

    udocker_path = os.path.join(docker_install_dir, "udocker")
    os.chdir(test_cwd)
    os.environ = test_environ
    return udocker_path


@pytest.mark.skipif(not LINUX, reason="LINUX only")
def test_udocker_usage_should_not_write_cid_file(udocker: str, tmp_path: Path) -> None:
    """Confirm that no cidfile is made when udocker is used."""
    cwd = Path.cwd()
    os.chdir(tmp_path)

    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    error_code, stdout, stderr = get_main_output(
        [
            "--debug",
            "--default-container",
            "debian",
            "--user-space-docker-cmd=" + udocker,
            get_data(test_file),
            get_data(job_file),
        ]
    )

    cidfiles_count = sum(1 for _ in tmp_path.glob("*.cid"))
    os.chdir(cwd)

    assert "completed success" in stderr, stderr
    assert cidfiles_count == 0


@pytest.mark.skipif(
    not LINUX or TRAVIS,
    reason="Linux only & not reliable on single threaded test on Travis-CI.",
)
def test_udocker_should_display_memory_usage(udocker: str, tmp_path: Path) -> None:
    """Confirm that memory ussage is logged even with udocker."""
    cwd = Path.cwd()
    os.chdir(tmp_path)
    error_code, stdout, stderr = get_main_output(
        [
            "--enable-ext",
            "--default-container=debian",
            "--user-space-docker-cmd=" + udocker,
            get_data("tests/wf/timelimit.cwl"),
            "--sleep_time",
            "10",
        ]
    )
    os.chdir(cwd)

    assert "completed success" in stderr, stderr
    assert "Max memory" in stderr, stderr
