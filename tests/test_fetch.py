import os
import urllib

import pytest

import schema_salad.main
import schema_salad.ref_resolver
import schema_salad.schema
from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.resolver import Path, resolve_local
from cwltool.utils import onWindows
from cwltool.workflow import default_make_tool
from schema_salad.tests.other_fetchers import CWLTestFetcher

from .util import get_data, working_directory


def test_fetcher():
    def test_resolver(d, a):
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


def norm(uri):
    if onWindows():
        return uri.lower()
    return uri


@pytest.mark.parametrize("path,expected_path", path_fragments)
def test_resolve_local(path, expected_path):
    with working_directory(root):
        expected = norm(root.as_uri() + expected_path)
        assert norm(resolve_local(None, path)) == expected
