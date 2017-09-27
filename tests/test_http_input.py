from __future__ import absolute_import
import unittest
import os
import tempfile
from cwltool.pathmapper import PathMapper


class TestHttpInput(unittest.TestCase):
    def test_http_path_mapping(self):
        class SubPathMapper(PathMapper):
            def __init__(self, referenced_files, basedir, stagedir):
                super(SubPathMapper, self).__init__(referenced_files, basedir, stagedir)
        input_file_path = "https://raw.githubusercontent.com/common-workflow-language/cwltool/master/tests/2.fasta"
        tempdir = tempfile.mkdtemp()
        base_file = [{
            "class": "File",
            "location": "https://raw.githubusercontent.com/common-workflow-language/cwltool/master/tests/2.fasta",
            "basename": "chr20.fa"
        }]
        path_map_obj = SubPathMapper(base_file, os.getcwd(), tempdir)

        self.assertIn(input_file_path,path_map_obj._pathmap)
        assert os.path.exists(path_map_obj._pathmap[input_file_path].resolved) == 1
        with open(path_map_obj._pathmap[input_file_path].resolved) as f:
            self.assertIn(">Sequence 561 BP; 135 A; 106 C; 98 G; 222 T; 0 other;",f.read())
            f.close()