from __future__ import absolute_import
import os

from pkg_resources import (Requirement, ResolutionError,  # type: ignore
                           resource_filename)
import distutils.spawn
import pytest

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
        # warning, __file__ is all lowercase on Windows systems, this can
        # sometimes conflict with docker toolkit. Workaround: pip install .
        # and run the tests elsewhere via python -m pytest --pyarg cwltool
    return filepath


needs_docker = pytest.mark.skipif(not bool(distutils.spawn.find_executable('docker')),
                                  reason="Requires the docker executable on the "
                                  "system path.")
