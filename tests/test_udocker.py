"""Test optional udocker feature."""

import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory

from .util import get_data, get_main_output, working_directory

LINUX = sys.platform in ("linux", "linux2")
UDOCKER_VERSION = "1.3.12"


@pytest.fixture(scope="session")
def udocker(tmp_path_factory: TempPathFactory) -> str:
    """Udocker fixture, returns the path to the udocker script."""
    test_environ = copy.copy(os.environ)
    docker_install_dir = str(tmp_path_factory.mktemp("udocker"))
    with working_directory(docker_install_dir):
        url = (
            "https://github.com/indigo-dc/udocker/releases/download/"
            f"{UDOCKER_VERSION}/udocker-{UDOCKER_VERSION}.tar.gz"
        )
        install_cmds = [
            ["curl", "-L", url, "-o", "./udocker-tarball.tgz"],
            ["tar", "--strip-components=1", "-xzvf", "udocker-tarball.tgz"],
            ["./udocker/udocker", "install"],
        ]

        test_environ["UDOCKER_DIR"] = os.path.join(docker_install_dir, ".udocker")
        test_environ["HOME"] = docker_install_dir

        results = []
        for _ in range(3):
            results = [subprocess.call(cmds, env=test_environ) for cmds in install_cmds]
            if sum(results) == 0:
                break
            subprocess.call(["rm", "-Rf", "./udocker"])

        assert sum(results) == 0

        udocker_path = os.path.join(docker_install_dir, "udocker/udocker")

    return udocker_path


@pytest.mark.skipif(not LINUX, reason="LINUX only")
def test_udocker_usage_should_not_write_cid_file(udocker: str, tmp_path: Path) -> None:
    """Confirm that no cidfile is made when udocker is used."""

    with working_directory(tmp_path):
        test_file = "tests/echo.cwl"
        error_code, stdout, stderr = get_main_output(
            [
                "--debug",
                "--default-container",
                "debian:stable-slim",
                "--user-space-docker-cmd=" + udocker,
                get_data(test_file),
                "--inp",
                "hello",
            ]
        )

        cidfiles_count = sum(1 for _ in tmp_path.glob("*.cid"))

    assert "completed success" in stderr, stderr
    assert cidfiles_count == 0


@pytest.mark.skipif(
    not LINUX or "GITHUB" in os.environ,
    reason="Linux only",
)
def test_udocker_should_display_memory_usage(udocker: str, tmp_path: Path) -> None:
    """Confirm that memory ussage is logged even with udocker."""
    with working_directory(tmp_path):
        error_code, stdout, stderr = get_main_output(
            [
                "--enable-ext",
                "--default-container=debian:stable-slim",
                "--user-space-docker-cmd=" + udocker,
                get_data("tests/wf/timelimit.cwl"),
                "--sleep_time",
                "10",
            ]
        )

    assert "completed success" in stderr, stderr
    assert "Max memory" in stderr, stderr


@pytest.mark.skipif(not LINUX, reason="LINUX only")
def test_udocker_nobanner(udocker: str, tmp_path: Path) -> None:
    """Avoid the banner when running udocker."""
    with working_directory(tmp_path):
        error_code, stdout, stderr = get_main_output(
            [
                "--user-space-docker-cmd=" + udocker,
                get_data("tests/wf/cat-tool.cwl"),
                get_data("tests/wf/wc-job.json"),
            ]
        )

    assert "completed success" in stderr, stderr
    assert "sha1$327fc7aedf4f6b69a42a7c8b808dc5a7aff61376" in stdout, stdout
