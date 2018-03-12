from __future__ import absolute_import
import unittest

from cwltool.main import main

from .util import get_data

class CWL_Version_Checks(unittest.TestCase):
    # no cwlVersion in the workflow
    def test_missing_cwl_version(self):
        self.assertEqual(main([get_data('tests/wf/missing_cwlVersion.cwl')]), 1)
    # using cwlVersion: v0.1 in the workflow
    def test_incorrect_cwl_version(self):
        self.assertEqual(main([get_data('tests/wf/wrong_cwlVersion.cwl')]), 1)
