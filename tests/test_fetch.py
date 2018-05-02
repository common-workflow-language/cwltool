from __future__ import absolute_import
import unittest
import sys
import os

from six.moves import urllib

import schema_salad.main
import schema_salad.ref_resolver
import schema_salad.schema
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.workflow import defaultMakeTool
from cwltool.resolver import resolve_local

if sys.version_info < (3, 4):
    from pathlib2 import Path
else:
    from pathlib import Path

from .util import get_data

class FetcherTest(unittest.TestCase):
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


        load_tool("foo.cwl", defaultMakeTool, resolver=test_resolver, fetcher_constructor=TestFetcher)

        self.assertEquals(0, main(["--print-pre", "--debug", "foo.cwl"], resolver=test_resolver,
                                  fetcher_constructor=TestFetcher))


class ResolverTest(unittest.TestCase):
    def test_resolve_local(self):
        real = os.path.realpath(get_data(""))
        rootdir = Path(real).as_uri()
        self.assertEqual(rootdir+"/tests/echo.cwl", resolve_local(None, get_data("tests/echo.cwl")))
        self.assertEqual(rootdir+"/tests/echo.cwl#main", resolve_local(None, get_data("tests/echo.cwl#main")))
        self.assertEqual(rootdir+"/tests/echo.cwl", resolve_local(None, real+"/tests/echo.cwl"))
        self.assertEqual(rootdir+"/tests/echo.cwl#main", resolve_local(None, real+"/tests/echo.cwl#main"))
