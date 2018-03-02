from __future__ import absolute_import

import unittest

from mock import Mock

import cwltool
import cwltool.factory
# we should modify the subprocess imported from cwltool.sandboxjs
from cwltool.sandboxjs import (check_js_threshold_version,
                               subprocess)
from .util import get_data


class Javascript_Sanity_Checks(unittest.TestCase):

    def setUp(self):
        self.check_output = subprocess.check_output 

    def tearDown(self):
        subprocess.check_output = self.check_output

    def test_node_version(self):
        subprocess.check_output = Mock(return_value=b'v0.8.26\n')
        self.assertEquals(check_js_threshold_version('node'), False)

        subprocess.check_output = Mock(return_value=b'v0.10.25\n')
        self.assertEquals(check_js_threshold_version('node'), False)

        subprocess.check_output = Mock(return_value=b'v0.10.26\n')
        self.assertEquals(check_js_threshold_version('node'), True)

        subprocess.check_output = Mock(return_value=b'v4.4.2\n')
        self.assertEquals(check_js_threshold_version('node'), True)

        subprocess.check_output = Mock(return_value=b'v7.7.3\n')
        self.assertEquals(check_js_threshold_version('node'), True)

    def test_is_javascript_installed(self):
            pass


class TestValueFrom(unittest.TestCase):

    def test_value_from_two_concatenated_expressions(self):
        f = cwltool.factory.Factory()
        echo = f.make(get_data("tests/wf/vf-concat.cwl"))
        self.assertEqual(echo(), {u"out": u"a sting\n"})
