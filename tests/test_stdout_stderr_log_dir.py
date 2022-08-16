import json
from pathlib import Path

from .util import get_data, get_main_output


def test_log_dir_echo_output(tmp_path: Path) -> None:
    _, stdout, stderr = get_main_output(
        ["--log-dir", str(tmp_path), get_data("tests/echo.cwl"), "--inp", "hello"]
    )
    assert "completed success" in stderr, stderr
    assert json.loads(stdout)["out"].strip("\n") == "hello"
    assert len(list(tmp_path.iterdir())) == 1
    subdir = next(tmp_path.iterdir())
    assert subdir.is_dir()
    assert len(list(subdir.iterdir())) == 1
    result = next(subdir.iterdir())
    assert result.name == "out.txt"
    output = open(result).read()
    assert output == "hello\n"


def test_log_dir_echo_no_output(tmp_path: Path) -> None:
    _, stdout, stderr = get_main_output(
        [
            "--log-dir",
            str(tmp_path),
            get_data("tests/echo-stdout-log-dir.cwl"),
            "--inp",
            "hello",
        ]
    )
    assert len(list(tmp_path.iterdir())) == 1
    subdir = next(tmp_path.iterdir())
    assert subdir.name == "echo"
    assert subdir.is_dir()
    assert len(list(subdir.iterdir())) == 1
    result = next(subdir.iterdir())
    assert result.name == "out.txt"
    output = open(result).read()
    assert output == "hello\n"


def test_log_dir_echo_stderr(tmp_path: Path) -> None:
    _, stdout, stderr = get_main_output(
        [
            "--log-dir",
            str(tmp_path),
            get_data("tests/echo-stderr.cwl"),
            "--message",
            "hello",
        ]
    )
    assert len(list(tmp_path.iterdir())) == 1
    subdir = next(tmp_path.iterdir())
    assert subdir.name == "echo-stderr.cwl"
    assert subdir.is_dir()
    assert len(list(subdir.iterdir())) == 1
    result = next(subdir.iterdir())
    assert result.name == "out.txt"
    output = open(result).read()
    assert output == "hello\n"
