"""Test user experience running on MS Windows."""

import os

import pytest

from cwltool import main

# Can't be just "import cwltool ; … cwltool.main.windows_check()"
# needs a direct import to avoid path traversal after os.name is set to "nt"


def test_windows_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm that the windows warning is given."""
    with pytest.warns(UserWarning, match=r"Windows Subsystem for Linux 2"):
        # would normally just use the MonkeyPatch object directly
        # but if we don't use a context then os.name being "nt" causes problems
        # for pytest on non-Windows systems. So the context unravels the change
        # to os.name quickly, and then pytest will check for the desired warning
        with monkeypatch.context() as m:
            m.setattr(os, "name", "nt")
            main.windows_check()
