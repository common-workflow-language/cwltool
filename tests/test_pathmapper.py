import unittest
import json
import cwltool.draft2tool as tool
import cwltool.expression as expr
import cwltool.factory
from cwltool.pathmapper import PathMapper


class TestPathMapper(unittest.TestCase):

    def test_subclass(self):

        class SubPathMapper(PathMapper):

            def __init__(self, referenced_files, basedir, stagedir, new):
                super(SubPathMapper, self).__init__(referenced_files, basedir, stagedir)
                self.new = new

        a = SubPathMapper([], '', '', "new")
        self.assertTrue(a.new, "new")
