import os
import json
from pathlib import Path

from cwltool.main import main

from .util import get_main_output, needs_docker


def test_log_dir_echo_output() -> None:
    _, stdout, stderr = get_main_output(
        ["--log-dir", "logs", "tests/echo.cwl", "--inp", "hello"]
    )
    assert "completed success" in stderr, stderr
    assert json.loads(stdout)["out"].strip("\n") == "hello"


def test_log_dir_echo_no_output() -> None:
    _, stdout, stderr = get_main_output(
        ["--log-dir", "logs", "tests/echo-stdout-log-dir.cwl", "--inp", "hello"]
    )
    for dir in os.listdir("logs"):
        for file in os.listdir(f"logs/{dir}"):
            assert file == "out.txt"
