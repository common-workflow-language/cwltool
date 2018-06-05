from __future__ import absolute_import
import unittest
import os
import sys

from cwltool.main import main
from cwltool.utils import subprocess

from .util import get_data


class RDFPrint(unittest.TestCase):
    """ Test `cwltool --print-rdf`. """

    def test_rdf_print(self):
        self.assertEquals(main(['--print-rdf', get_data('tests/wf/hello_single_tool.cwl')]), 0)

    def test_rdf_print_unicode(self):
        """Force ASCII encoding but load UTF file with --print-rdf."""
        lc_all = os.environ.get("LC_ALL", None)
        os.environ["LC_ALL"] = "C"
        self.assertEquals(subprocess.check_call(
            [sys.executable, "-m", "cwltool", '--print-rdf',
             get_data('tests/utf_doc_example')]), 0)
        if lc_all:
            os.environ["LC_ALL"] = lc_all
