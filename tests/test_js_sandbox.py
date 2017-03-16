import unittest
from mock import Mock

# we should modify the subprocess imported from cwltool.sandboxjs
from cwltool.sandboxjs import check_js_threshold_version, subprocess

class Javascript_Sanity_Checks(unittest.TestCase):

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
