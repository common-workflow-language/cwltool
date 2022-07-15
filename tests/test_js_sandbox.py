"""Test sandboxjs.py and related code."""
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any, List

import pytest
from cwl_utils import sandboxjs

from cwltool.factory import Factory
from cwltool.loghandler import _logger, configure_logging

from .util import get_data, needs_podman, needs_singularity

node_versions = [
    ("v0.8.26\n", False),
    ("v0.10.25\n", False),
    ("v0.10.26\n", True),
    ("v4.4.2\n", True),
    ("v7.7.3\n", True),
]

configure_logging(_logger.handlers[-1], False, True, True, True)
_logger.setLevel(logging.DEBUG)


@pytest.mark.parametrize("version,supported", node_versions)
def test_node_version(version: str, supported: bool, mocker: Any) -> None:
    mocked_subprocess = mocker.patch("cwl_utils.sandboxjs.subprocess")
    mocked_subprocess.check_output = mocker.Mock(return_value=version)

    assert sandboxjs.check_js_threshold_version("node") == supported


def test_value_from_two_concatenated_expressions() -> None:
    js_engine = sandboxjs.get_js_engine()
    js_engine.have_node_slim = False  # type: ignore[attr-defined]
    js_engine.localdata = threading.local()  # type: ignore[attr-defined]
    factory = Factory()
    echo = factory.make(get_data("tests/wf/vf-concat.cwl"))
    file = {"class": "File", "location": get_data("tests/wf/whale.txt")}

    assert echo(file1=file) == {"out": "a string\n"}


def hide_nodejs(temp_dir: Path) -> str:
    """Generate a new PATH that hides node{js,}."""
    paths: List[str] = os.environ.get("PATH", "").split(":")
    names: List[str] = []
    for name in ("nodejs", "node"):
        path = shutil.which(name)
        if path:
            names.append(path)
    for name in names:
        dirname = os.path.dirname(name)
        if dirname in paths:
            paths.remove(dirname)
            new_dir = temp_dir / os.path.basename(dirname)
            new_dir.mkdir()
            for entry in os.listdir(dirname):
                if entry not in ("nodejs", "node"):
                    os.symlink(os.path.join(dirname, entry), new_dir / entry)
            paths.append(str(new_dir))
    return ":".join(paths)


@needs_podman
def test_value_from_two_concatenated_expressions_podman(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Javascript test using podman."""
    js_engine = sandboxjs.get_js_engine()
    js_engine.have_node_slim = False  # type: ignore[attr-defined]
    js_engine.localdata = threading.local()  # type: ignore[attr-defined]
    new_paths = hide_nodejs(tmp_path)
    factory = Factory()
    factory.loading_context.podman = True
    factory.loading_context.debug = True
    factory.runtime_context.debug = True
    with monkeypatch.context() as m:
        m.setenv("PATH", new_paths)
        echo = factory.make(get_data("tests/wf/vf-concat.cwl"))
        file = {"class": "File", "location": get_data("tests/wf/whale.txt")}
        assert echo(file1=file) == {"out": "a string\n"}


@needs_singularity
def test_value_from_two_concatenated_expressions_singularity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Javascript test using Singularity."""
    js_engine = sandboxjs.get_js_engine()
    js_engine.have_node_slim = False  # type: ignore[attr-defined]
    js_engine.localdata = threading.local()  # type: ignore[attr-defined]
    new_paths = hide_nodejs(tmp_path)
    factory = Factory()
    factory.loading_context.singularity = True
    factory.loading_context.debug = True
    factory.runtime_context.debug = True
    with monkeypatch.context() as m:
        m.setenv("PATH", new_paths)
        echo = factory.make(get_data("tests/wf/vf-concat.cwl"))
        file = {"class": "File", "location": get_data("tests/wf/whale.txt")}
        assert echo(file1=file) == {"out": "a string\n"}


def test_caches_js_processes(mocker: Any) -> None:
    sandboxjs.exec_js_process("7", context="{}")

    mocked_new_js_proc = mocker.patch("cwl_utils.sandboxjs.new_js_proc")
    sandboxjs.exec_js_process("7", context="{}")

    mocked_new_js_proc.assert_not_called()
