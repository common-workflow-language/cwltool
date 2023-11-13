import os
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urljoin, urlsplit

import pytest
import requests
from schema_salad.fetcher import Fetcher
from schema_salad.utils import CacheType

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.resolver import resolve_local
from cwltool.workflow import default_make_tool

from .util import get_data, working_directory


class CWLTestFetcher(Fetcher):
    def __init__(
        self,
        cache: CacheType,
        session: Optional[requests.sessions.Session],
    ) -> None:
        """Create a Fetcher that provides a fixed result for testing purposes."""

    def fetch_text(self, url: str, content_types: Optional[List[str]] = None) -> str:
        if url == "baz:bar/foo.cwl":
            return """
cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo
inputs: []
outputs: []
"""
        raise RuntimeError("Not foo.cwl, was %s" % url)

    def check_exists(self, url):  # type: (str) -> bool
        return url == "baz:bar/foo.cwl"

    def urljoin(self, base: str, url: str) -> str:
        urlsp = urlsplit(url)
        if urlsp.scheme:
            return url
        basesp = urlsplit(base)

        if basesp.scheme == "keep":
            return base + "/" + url
        return urljoin(base, url)


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

    assert main(["--print-pre", "--debug", "foo.cwl"], loadingContext=loadingContext) == 0


root = Path(os.path.join(get_data("")))

path_fragments = [
    (os.path.join("tests", "echo.cwl"), "/tests/echo.cwl"),
    (os.path.join("tests", "echo.cwl") + "#main", "/tests/echo.cwl#main"),
    (str(root / "tests" / "echo.cwl"), "/tests/echo.cwl"),
    (str(root / "tests" / "echo.cwl") + "#main", "/tests/echo.cwl#main"),
]


@pytest.mark.parametrize("path,expected_path", path_fragments)
def test_resolve_local(path: str, expected_path: str) -> None:
    with working_directory(root):
        expected = root.as_uri() + expected_path
        resolved = resolve_local(None, path)
        assert resolved
        assert resolved == expected
