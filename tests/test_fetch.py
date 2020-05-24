import os
from pathlib import Path
from typing import Any

import pytest  # type: ignore
from schema_salad.tests.other_fetchers import CWLTestFetcher

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.resolver import resolve_local
from cwltool.utils import onWindows
from cwltool.workflow import default_make_tool

from .util import get_data, working_directory


def test_fetcher() -> None:
    def test_resolver(d: Any, a: str) -> str:
        if a.startswith("baz:bar/"):
            return a
        return "baz:bar/" + a

    loadingContext = LoadingContext(
        {
            "construct_tool_object": default_make_tool,
            "resolver": test_resolver,
            "fetcher_constructor": CWLTestFetcher,
        }
    )

    load_tool("foo.cwl", loadingContext)

    assert (
        main(["--print-pre", "--debug", "foo.cwl"], loadingContext=loadingContext) == 0
    )


root = Path(os.path.join(get_data("")))

path_fragments = [
    (os.path.join("tests", "echo.cwl"), "/tests/echo.cwl"),
    (os.path.join("tests", "echo.cwl") + "#main", "/tests/echo.cwl#main"),
    (str(root / "tests" / "echo.cwl"), "/tests/echo.cwl"),
    (str(root / "tests" / "echo.cwl") + "#main", "/tests/echo.cwl#main"),
]


def norm(uri: str) -> str:
    if onWindows():
        return uri.lower()
    return uri


@pytest.mark.parametrize("path,expected_path", path_fragments)  # type: ignore
def test_resolve_local(path: str, expected_path: str) -> None:
    with working_directory(root):
        expected = norm(root.as_uri() + expected_path)
        resolved = resolve_local(None, path)
        assert resolved
        assert norm(resolved) == expected
