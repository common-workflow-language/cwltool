from __future__ import absolute_import
import unittest

import os
import tempfile
from six import StringIO
from cwltool.main import main
import shutil

from .util import get_data

class TestProvenance(unittest.TestCase):

    folder = None

    def setUp(self):
        self.folder = tempfile.mkdtemp("ro")
        if os.environ.get("DEBUG"):
            print("%s folder: %s" % (this, self.folder))

    def tearDown(self):
        if self.folder and not os.environ.get("DEBUG"):
            shutil.rmtree(self.folder)

    def test_hello_workflow(self):
        self.assertEquals(main(['--provenance', self.folder, get_data('tests/wf/hello-workflow.cwl'),
            "--usermessage", "Hello workflow"]), 0)

    def test_hello_single_tool(self):
        self.assertEquals(main(['--provenance', self.folder, get_data('tests/wf/hello_single_tool.cwl'), 
            "--message", "Hello tool"]), 0)

    def test_revsort_workflow(self):
        self.assertEquals(main(['--provenance', self.folder, get_data('tests/wf/revsort.cwl'),
            get_data('tests/wf/revsort-job.json')]), 0)
