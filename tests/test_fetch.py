from __future__ import absolute_import

import os
import unittest

import schema_salad.main
import schema_salad.ref_resolver
import schema_salad.schema
from six.moves import urllib

from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.resolver import Path, resolve_local
from cwltool.utils import onWindows
from cwltool.workflow import default_make_tool
from cwltool.context import LoadingContext

from .util import get_data


class FetcherTest(unittest.TestCase):
    """Test using custom schema_salad.ref_resolver.Fetcher."""
    def test_fetcher(self):
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
                else:
                    raise RuntimeError("Not foo.cwl, was %s" % url)

            def check_exists(self, url):  # type: (unicode) -> bool
                if url == "baz:bar/foo.cwl":
                    return True
                else:
                    return False

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
            else:
                return "baz:bar/" + a

        loadingContext = LoadingContext({"construct_tool_object": default_make_tool,
                                         "resolver": test_resolver,
                                         "fetcher_constructor": TestFetcher})

        load_tool("foo.cwl", loadingContext)

        self.assertEquals(0, main(["--print-pre", "--debug", "foo.cwl"], loadingContext=loadingContext))


class ResolverTest(unittest.TestCase):
    def test_resolve_local(self):
        origpath = os.getcwd()
        os.chdir(os.path.join(get_data("")))

        def norm(uri):
            if onWindows():
                return uri.lower()
            else:
                return uri
        try:
            root = Path.cwd()
            rooturi = root.as_uri()
            self.assertEqual(norm(rooturi+"/tests/echo.cwl"),
                    norm(resolve_local(None, os.path.join("tests",
                        "echo.cwl"))))
            self.assertEqual(norm(rooturi+"/tests/echo.cwl#main"),
                    norm(resolve_local(None, os.path.join("tests",
                        "echo.cwl")+"#main")))
            self.assertEqual(norm(rooturi+"/tests/echo.cwl"),
                    norm(resolve_local(None, str(root / "tests" /
                        "echo.cwl"))))
            self.assertEqual(norm(rooturi+"/tests/echo.cwl#main"),
                    norm(resolve_local(None, str(root / "tests" /
                        "echo.cwl")+"#main")))
        finally:
            os.chdir(origpath)
