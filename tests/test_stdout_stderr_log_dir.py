import os
import json
from pathlib import Path

from cwltool.main import main

from .util import get_main_output, needs_docker

def test_log_dir_echo_output() -> None:
    _, stdout, stderr = get_main_output(
        [
            "--log-dir",
            "logs",
            "tests/echo.cwl",
            "--inp", "hello"
        ]
    )
    assert "completed success" in stderr, stderr
    assert json.loads(stdout)['out'].strip('\n') == 'hello'
