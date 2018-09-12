import os

from six.moves import urllib

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

from .util import get_data, working_directory

def test_fetcher():
    class TestFetcher(schema_salad.ref_resolver.Fetcher):
        def __init__(self, a, b):
            pass

        def fetch_text(self, url):  # type: (unicode) -> unicode
            if url == "baz:bar/foo.cwl":
                return """
cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo
inputs: []
outputs: []
"""
            raise RuntimeError("Not foo.cwl, was %s" % url)

        def check_exists(self, url):  # type: (unicode) -> bool
            return  url == "baz:bar/foo.cwl"

        def urljoin(self, base, url):
            urlsp = urllib.parse.urlsplit(url)
            if urlsp.scheme:
                return url
            basesp = urllib.parse.urlsplit(base)

            if basesp.scheme == "keep":
                return base + "/" + url
            return urllib.parse.urljoin(base, url)

    def test_resolver(d, a):
        if a.startswith("baz:bar/"):
            return a
        return "baz:bar/" + a

    loadingContext = LoadingContext({"construct_tool_object": default_make_tool,
                                     "resolver": test_resolver,
                                     "fetcher_constructor": TestFetcher})

    load_tool("foo.cwl", loadingContext)

    assert main(["--print-pre", "--debug", "foo.cwl"], loadingContext=loadingContext) == 0

root = Path(os.path.join(get_data("")))

path_fragments = [
    (os.path.join("tests", "echo.cwl"), "/tests/echo.cwl"),
    (os.path.join("tests", "echo.cwl") + "#main", "/tests/echo.cwl#main"),
    (str(root / "tests" / "echo.cwl"), "/tests/echo.cwl"),
    (str(root / "tests" / "echo.cwl") + "#main", "/tests/echo.cwl#main")
]

@pytest.mark.parametrize('path,expected_path', path_fragments)
def test_resolve_local(path, expected_path):
    def norm(uri):
        if onWindows():
            return uri.lower()
        return uri

    with working_directory(root):
        expected = norm(root.as_uri() + expected_path)
        assert norm(resolve_local(None, path)) == expected
