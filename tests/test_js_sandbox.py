from __future__ import absolute_import

import unittest

import pytest
from mock import Mock, patch

import cwltool
import cwltool.factory
import cwltool.sandboxjs
# we should modify the subprocess imported from cwltool.sandboxjs
from cwltool.sandboxjs import (check_js_threshold_version, exec_js_process,
                               subprocess)
from cwltool.utils import onWindows

from .util import get_data, get_windows_safe_factory, windows_needs_docker


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

    @windows_needs_docker
    def test_value_from_two_concatenated_expressions(self):
        f = get_windows_safe_factory()
        echo = f.make(get_data("tests/wf/vf-concat.cwl"))
        self.assertEqual(echo(file1={
            "class": "File",
            "location": get_data("tests/wf/whale.txt")}),
            {u"out": u"a string\n"})


class ExecJsProcessTest(unittest.TestCase):
    @pytest.mark.skipif(onWindows(),
                        reason="Caching processes for windows is not supported.")
    def test_caches_js_processes(self):
        exec_js_process("7", context="{}")

        with patch("cwltool.sandboxjs.new_js_proc", new=Mock(wraps=cwltool.sandboxjs.new_js_proc)) as mock:
            exec_js_process("7", context="{}")
            mock.assert_not_called()
