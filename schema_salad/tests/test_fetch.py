import unittest
import schema_salad.ref_resolver
import schema_salad.main
import schema_salad.schema
from schema_salad.jsonld_context import makerdf
from pkg_resources import Requirement, resource_filename, ResolutionError  # type: ignore
import rdflib
import ruamel.yaml as yaml
import json
import os

class TestFetcher(unittest.TestCase):
    def test_fetcher(self):
        class TestFetcher(schema_salad.ref_resolver.Fetcher):
            def __init__(self, a, b):
                pass

            def fetch_text(self, url):    # type: (unicode) -> unicode
                print url
                if url.endswith("foo.txt"):
                    return "hello: foo"
                else:
                    raise RuntimeError("Not foo.txt")

            def check_exists(self, url):  # type: (unicode) -> bool
                if url.endswith("foo.txt"):
                    return True
                else:
                    return False

        loader = schema_salad.ref_resolver.Loader({}, fetcher_constructor=TestFetcher)
        self.assertEqual({"hello": "foo"}, loader.resolve_ref("foo.txt")[0])
        self.assertTrue(loader.check_exists("foo.txt"))

        with self.assertRaises(RuntimeError):
            loader.resolve_ref("bar.txt")
        self.assertFalse(loader.check_exists("bar.txt"))

    def test_cache(self):
        loader = schema_salad.ref_resolver.Loader({})
        foo = "file://%s/foo.txt" % os.getcwd()
        loader.cache.update({foo: "hello: foo"})
        print loader.cache
        self.assertEqual({"hello": "foo"}, loader.resolve_ref("foo.txt")[0])
        self.assertTrue(loader.check_exists(foo))
