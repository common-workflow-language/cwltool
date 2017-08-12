from __future__ import absolute_import
import unittest

from six import StringIO
from cwltool.main import main

from .util import get_data

class RDF_Print(unittest.TestCase):

    def test_rdf_print(self):
        self.assertEquals(main(['--print-rdf', get_data('tests/wf/hello_single_tool.cwl')]), 0)
