"""Test functions."""

import atexit
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Dict, Generator, List, Mapping, Optional, Tuple, Union

import pytest

from cwltool.env_to_stdout import deserialize_env
from cwltool.main import main
from cwltool.singularity import is_version_2_6, is_version_3_or_newer
from cwltool.utils import as_file, files


def force_default_container(default_container_id: str, _: str) -> str:
    return default_container_id


def get_data(filename: str) -> str:
    # normalizing path depending on OS or else it will cause problem when joining path
    filename = os.path.normpath(filename)
    filepath = None
    try:
        file_manager = ExitStack()
        atexit.register(file_manager.close)
        traversable = files("cwltool") / filename
        filepath = file_manager.enter_context(as_file(traversable))
    except ModuleNotFoundError:
        pass
    if not filepath or not os.path.isfile(filepath):
        filepath = Path(os.path.dirname(__file__)) / ".." / filename
    return str(filepath.resolve())


needs_docker = pytest.mark.skipif(
    not bool(shutil.which("docker")),
    reason="Requires the docker executable on the system path.",
)

needs_singularity = pytest.mark.skipif(
    not bool(shutil.which("singularity")),
    reason="Requires the singularity executable on the system path.",
)

needs_singularity_2_6 = pytest.mark.skipif(
    not bool(shutil.which("singularity") and is_version_2_6()),
    reason="Requires that version 2.6.x of singularity executable version is on the system path.",
)

needs_singularity_3_or_newer = pytest.mark.skipif(
    (not bool(shutil.which("singularity"))) or (not is_version_3_or_newer()),
    reason="Requires that version 3.x of singularity executable version is on the system path.",
)

needs_podman = pytest.mark.skipif(
    not bool(shutil.which("podman")),
    reason="Requires the podman executable on the system path.",
)

_env_accepts_null: Optional[bool] = None


def env_accepts_null() -> bool:
    """Return True iff the env command on this host accepts `-0`."""
    global _env_accepts_null
    if _env_accepts_null is None:
        result = subprocess.run(
            ["env", "-0"],
            capture_output=True,
            encoding="utf-8",
        )
        _env_accepts_null = result.returncode == 0

    return _env_accepts_null


def get_main_output(
    args: List[str],
    replacement_env: Optional[Mapping[str, str]] = None,
    extra_env: Optional[Mapping[str, str]] = None,
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
) -> Tuple[Optional[int], str, str]:
    """Run cwltool main.

    args: the command line args to call it with

    replacement_env: a total replacement of the environment

    extra_env: add these to the environment used

    monkeypatch: required if changing the environment

    Returns (return code, stdout, stderr)
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    if replacement_env is not None:
        assert monkeypatch is not None
        monkeypatch.setattr(os, "environ", replacement_env)

    if extra_env is not None:
        assert monkeypatch is not None
        for k, v in extra_env.items():
            monkeypatch.setenv(k, v)

    try:
        rc = main(argsl=args, stdout=stdout, stderr=stderr)
    except SystemExit as e:
        if isinstance(e.code, int):
            rc = e.code
        else:
            rc = sys.maxsize
    return (
        rc,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def get_tool_env(
    tmp_path: Path,
    flag_args: List[str],
    inputs_file: Optional[str] = None,
    replacement_env: Optional[Mapping[str, str]] = None,
    extra_env: Optional[Mapping[str, str]] = None,
    monkeypatch: Optional[pytest.MonkeyPatch] = None,
    runtime_env_accepts_null: Optional[bool] = None,
) -> Dict[str, str]:
    """Get the env vars for a tool's invocation."""
    # GNU env accepts the -0 option to end each variable's
    # printing with "\0". No such luck on BSD-ish.
    #
    # runtime_env_accepts_null is None => figure it out, otherwise
    # use wrapped bool (because containers).
    if runtime_env_accepts_null is None:
        runtime_env_accepts_null = env_accepts_null()

    args = flag_args.copy()
    if runtime_env_accepts_null:
        args.append(get_data("tests/env3.cwl"))
    else:
        args.append(get_data("tests/env4.cwl"))

    if inputs_file is not None:
        args.append(inputs_file)

    with working_directory(tmp_path):
        rc, stdout, stderr = get_main_output(
            args,
            replacement_env=replacement_env,
            extra_env=extra_env,
            monkeypatch=monkeypatch,
        )
        assert rc == 0, stdout + "\n" + stderr

        output = json.loads(stdout)
        with open(output["env"]["path"]) as _:
            return deserialize_env(_.read())


@contextlib.contextmanager
def working_directory(path: Union[str, Path]) -> Generator[None, None, None]:
    """Change working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
