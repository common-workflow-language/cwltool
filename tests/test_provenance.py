from __future__ import absolute_import
import unittest

import os
import tempfile
from six import StringIO
from cwltool.main import main
import shutil
import pytest
from cwltool.utils import onWindows

# Module to be tested
from cwltool import provenance

from .util import get_data
import bagit
import posixpath
import ntpath

@pytest.mark.skipif(onWindows(),
                    reason="On Windows this would invoke a default docker container")
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
        self.check_ro()

    def test_hello_single_tool(self):
        self.assertEquals(main(['--provenance', self.folder, get_data('tests/wf/hello_single_tool.cwl'), 
            "--message", "Hello tool"]), 0)
        self.check_ro()            

    def test_revsort_workflow(self):
        self.assertEquals(main(['--no-container', '--provenance', self.folder, get_data('tests/wf/revsort.cwl'),
            get_data('tests/wf/revsort-job.json')]), 0)
        self.check_ro()            

    def check_ro(self):
        # Our folders
        for d in ("data", "snapshot", "workflow", "metadata", os.path.join("metadata", "provenance")):
            f = os.path.join(self.folder, d)
            self.assertTrue(os.path.isdir(f))
        
        # check bagit structure
        for f in ("bagit.txt", "bag-info.txt", "manifest-sha1.txt", "tagmanifest-sha1.txt", "tagmanifest-sha256.txt"):
            f = os.path.join(self.folder, f)
            self.assertTrue(os.path.isfile(f))
        bag = bagit.Bag(self.folder)
        self.assertTrue(bag.has_oxum())        
        (only_manifest, only_fs) = bag.compare_manifests_with_fs()
        self.assertFalse(list(only_manifest), "Some files only in manifest")
        self.assertFalse(list(only_fs), "Some files only on file system")
        missing_tagfiles = bag.missing_optional_tagfiles()
        self.assertFalse(list(missing_tagfiles), "Some files only in tagmanifest")
        bag.validate()

class TestConvertPath(unittest.TestCase):

    def nt_to_posix(self):
        self.assertEquals("a/b/c", 
            provenance._convert_path(r"a\b\c", ntpath, posixpath))
    
    def posix_to_nt(self):            
        self.assertEquals(r"a\b\c", 
            provenance._convert_path("a/b/c", posixpath, ntpath))

    def posix_to_posix(self):            
        self.assertEquals("a/b/c",
            provenance._convert_path("a/b/c", posixpath, posixpath))

    def nt_to_nt(self):
        self.assertEquals(r"a\b\c", 
            provenance._convert_path(r"a\b\c", ntpath, ntpath))

    def posix_to_nt_absolute_fails(self):            
        with self.assertRaises(ValueError):        
            provenance._convert_path("/absolute/path", posixpath, ntpath)
    
    def nt_to_posix_absolute_fails(self):            
        with self.assertRaises(ValueError):        
            provenance._convert_path(r"D:\absolute\path", ntpath, posixpath)

class TestWritableBagFile(unittest.TestCase):
    def setUp(self):
        self.ro = provenance.ResearchObject()

    def absolute_path_fails(self):
        with self.assertRaises(ValueError):
            self.ro.write_bag_file("/absolute/path/fails")