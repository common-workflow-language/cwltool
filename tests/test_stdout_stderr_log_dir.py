import os
import json
from pathlib import Path

from cwltool.main import main

from .util import get_data, get_main_output, needs_docker


def test_log_dir_echo_output(tmp_path: Path) -> None:
    _, stdout, stderr = get_main_output(
        ["--log-dir", str(tmp_path), get_data("tests/echo.cwl"), "--inp", "hello"]
    )
    assert "completed success" in stderr, stderr
    assert json.loads(stdout)["out"].strip("\n") == "hello"
    # and then check in `tmp_path` that there is no stdout log file, since `echo.cwl` uses `stdout` itself.
    # should there be an empty stderr log, though?


def test_log_dir_echo_no_output() -> None:
    _, stdout, stderr = get_main_output(
        [
            "--log-dir",
            "logs",
            get_data("tests/echo-stdout-log-dir.cwl"),
            "--inp",
            "hello",
        ]
    )
    for dir in os.listdir("logs"):
        for file in os.listdir(f"logs/{dir}"):
            assert file == "out.txt"
