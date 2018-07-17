from __future__ import absolute_import

import distutils.spawn  # pylint: disable=no-name-in-module,import-error
import functools
import os
from typing import Text

import pytest
from pkg_resources import (Requirement, ResolutionError,  # type: ignore
                           resource_filename)

from cwltool.factory import Factory
from cwltool.utils import onWindows, windows_default_container_id
from cwltool.context import RuntimeContext, LoadingContext
from cwltool.resolver import Path

def get_windows_safe_factory(runtime_context=None,  # type: RuntimeContext
                             loading_context=None,  # type: LoadingContext
                             executor=None          # type: Any
                            ):  # type: (...) -> Factory
    if onWindows():
        if not runtime_context:
            runtime_context = RuntimeContext()
        runtime_context.find_default_container = functools.partial(
            force_default_container, windows_default_container_id)
        runtime_context.use_container = True
        runtime_context.default_container = windows_default_container_id
    return Factory(executor, loading_context, runtime_context)

def force_default_container(default_container_id, builder):
    return default_container_id

def get_data(filename):
    filename = os.path.normpath(
        filename)  # normalizing path depending on OS or else it will cause problem when joining path
    filepath = None
    try:
        filepath = resource_filename(
            Requirement.parse("cwltool"), filename)
    except ResolutionError:
        pass
    if not filepath or not os.path.isfile(filepath):
        filepath = os.path.join(os.path.dirname(__file__), os.pardir, filename)
    return Text(Path(filepath).resolve())


needs_docker = pytest.mark.skipif(not bool(distutils.spawn.find_executable('docker')),
                                  reason="Requires the docker executable on the "
                                  "system path.")

needs_singularity = pytest.mark.skipif(not bool(distutils.spawn.find_executable('singularity')),
                                       reason="Requires the singularity executable on the "
                                       "system path.")

windows_needs_docker = pytest.mark.skipif(
    onWindows() and not bool(distutils.spawn.find_executable('docker')),
    reason="Running this test on MS Windows requires the docker executable "
    "on the system path.")
