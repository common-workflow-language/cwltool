import contextlib
import distutils.spawn  # pylint: disable=no-name-in-module,import-error
import functools
import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Generator, List, Mapping, Optional, Tuple, Union

import pytest
from pkg_resources import Requirement, ResolutionError, resource_filename

from cwltool.context import LoadingContext, RuntimeContext
from cwltool.executors import JobExecutor
from cwltool.factory import Factory
from cwltool.main import main
from cwltool.singularity import is_version_2_6, is_version_3_or_newer
from cwltool.utils import onWindows, windows_default_container_id


def get_windows_safe_factory(
    runtime_context: Optional[RuntimeContext] = None,
    loading_context: Optional[LoadingContext] = None,
    executor: Optional[JobExecutor] = None,
) -> Factory:
    if onWindows():
        if not runtime_context:
            runtime_context = RuntimeContext()
        runtime_context.find_default_container = functools.partial(
            force_default_container, windows_default_container_id
        )
        runtime_context.use_container = True
        runtime_context.default_container = windows_default_container_id
    return Factory(executor, loading_context, runtime_context)


def force_default_container(default_container_id: str, _: str) -> str:
    return default_container_id


def get_data(filename: str) -> str:
    # normalizing path depending on OS or else it will cause problem when joining path
    filename = os.path.normpath(filename)
    filepath = None
    try:
        filepath = resource_filename(Requirement.parse("cwltool"), filename)
    except ResolutionError:
        pass
    if not filepath or not os.path.isfile(filepath):
        filepath = os.path.join(os.path.dirname(__file__), os.pardir, filename)
    return str(Path(filepath).resolve())


needs_docker = pytest.mark.skipif(
    not bool(distutils.spawn.find_executable("docker")),
    reason="Requires the docker executable on the system path.",
)

needs_singularity = pytest.mark.skipif(
    not bool(distutils.spawn.find_executable("singularity")),
    reason="Requires the singularity executable on the system path.",
)

needs_singularity_2_6 = pytest.mark.skipif(
    not bool(distutils.spawn.find_executable("singularity") and is_version_2_6()),
    reason="Requires that version 2.6.x of singularity executable version is on the system path.",
)

needs_singularity_3_or_newer = pytest.mark.skipif(
    (not bool(distutils.spawn.find_executable("singularity")))
    or (not is_version_3_or_newer()),
    reason="Requires that version 3.x of singularity executable version is on the system path.",
)


windows_needs_docker = pytest.mark.skipif(
    onWindows() and not bool(distutils.spawn.find_executable("docker")),
    reason="Running this test on MS Windows requires the docker executable "
    "on the system path.",
)


def get_main_output(
    args: List[str],
    env: Union[
        Mapping[bytes, Union[bytes, str]], Mapping[str, Union[bytes, str]], None
    ] = None,
    monkeypatch: Any = None,
) -> Tuple[Optional[int], str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    if env is not None:
        assert monkeypatch is not None
        monkeypatch.setattr(os, "environ", env)
    try:
        rc = main(argsl=args, stdout=stdout, stderr=stderr)
    except SystemExit as e:
        rc = e.code
    return (
        rc,
        stdout.getvalue(),
        stderr.getvalue(),
    )


@contextlib.contextmanager
def working_directory(path: Union[str, Path]) -> Generator[None, None, None]:
    """Change working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
