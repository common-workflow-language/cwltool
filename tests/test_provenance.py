from __future__ import absolute_import
import unittest

from io import open
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

    def test_nt_to_posix(self):
        self.assertEquals("a/b/c", 
            provenance._convert_path(r"a\b\c", ntpath, posixpath))
    
    def test_posix_to_nt(self):            
        self.assertEquals(r"a\b\c", 
            provenance._convert_path("a/b/c", posixpath, ntpath))

    def test_posix_to_posix(self):            
        self.assertEquals("a/b/c",
            provenance._convert_path("a/b/c", posixpath, posixpath))

    def test_nt_to_nt(self):
        self.assertEquals(r"a\b\c", 
            provenance._convert_path(r"a\b\c", ntpath, ntpath))

    def test_posix_to_nt_absolute_fails(self):            
        with self.assertRaises(ValueError):        
            provenance._convert_path("/absolute/path", posixpath, ntpath)
    
    def test_nt_to_posix_absolute_fails(self):            
        with self.assertRaises(ValueError):        
            provenance._convert_path(r"D:\absolute\path", ntpath, posixpath)

class TestWritableBagFile(unittest.TestCase):
    def setUp(self):
        self.ro = provenance.ResearchObject()

    def tearDown(self):
        self.ro.close()

    def test_absolute_path_fails(self):
        with self.assertRaises(ValueError):
            self.ro.write_bag_file("/absolute/path/fails")

    def test_climboutfails(self):
        with self.assertRaises(ValueError):
            self.ro.write_bag_file("../../outside-ro")

    def test_writableString(self):
        with self.ro.write_bag_file("file.txt") as f1:
            self.assertTrue(f1.writable())
            f1.write(u"Hello\n")
            # TODO: Check Windows does not modify \n to \r\n here
        
        sha1 = os.path.join(self.ro.folder, "tagmanifest-sha1.txt")
        self.assertTrue(os.path.isfile(sha1))
        with open(sha1, "r", encoding="UTF-8") as f2:
            s = f2.readline().strip()
            self.assertTrue(s.endswith("file.txt"))
#stain@biggie:~/src/cwltool$ echo Hello | sha1sum
#1d229271928d3f9e2bb0375bd6ce5db6c6d348d9  -
            self.assertTrue(s.startswith("1d229271928d3f9e2bb0375bd6ce5db6c6d348d9"))

        sha256 = os.path.join(self.ro.folder, "tagmanifest-sha256.txt")
        self.assertTrue(os.path.isfile(sha256))
        with open(sha256, "r", encoding="UTF-8") as f3:
            s = f3.readline().strip()
            self.assertTrue(s.endswith("file.txt"))
#stain@biggie:~/src/cwltool$ echo Hello | sha256sum
#66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18  -
            self.assertTrue(s.startswith("66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18"))

        sha512 = os.path.join(self.ro.folder, "tagmanifest-sha512.txt")
        self.assertTrue(os.path.isfile(sha512))

    def test_writableUnicodeString(self):
        with self.ro.write_bag_file("file.txt") as f:
            self.assertTrue(f.writable())
            f.write(u"Here is a snowman: \u2603 \n")

    def test_writableBytes(self):
        with self.ro.write_bag_file("file.txt", encoding=None) as f:
            b = u"Here is a snowman: \u2603 \n".encode("UTF-8")
            f.write(b)

    def test_data(self):
        with self.ro.write_bag_file("data/file.txt") as f1:
            self.assertTrue(f1.writable())
            f1.write(u"Hello\n")
            # TODO: Check Windows does not modify \n to \r\n here
        
        # Because this is under data/ it should add to manifest
        # rather than tagmanifest
        sha1 = os.path.join(self.ro.folder, "manifest-sha1.txt")
        self.assertTrue(os.path.isfile(sha1))
        with open(sha1, "r", encoding="UTF-8") as f2:
            s = f2.readline().strip()
            self.assertTrue(s.endswith("data/file.txt"))

    def test_not_seekable(self):
        with self.ro.write_bag_file("file.txt") as f:
            self.assertFalse(f.seekable())
            with self.assertRaises(IOError):
                f.seek(0)

    def test_not_readable(self):
        with self.ro.write_bag_file("file.txt") as f:
            self.assertFalse(f.readable())
            with self.assertRaises(IOError):
                f.read()

    def test_truncate_fails(self):        
        with self.ro.write_bag_file("file.txt") as f:
            f.write(u"Hello there")
            f.truncate() # OK as we're always at end
            # Will fail because the checksum can't rewind
            with self.assertRaises(IOError):
                f.truncate(0)

class TestORCID(unittest.TestCase):
    def test_check_mod_11_2(self):
        # Taken from "Some sample ORCID iDs" on
        # https://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier
        self.assertTrue(provenance._check_mod_11_2("0000-0002-1825-0097"))
        self.assertTrue(provenance._check_mod_11_2("0000-0001-5109-3700"))
        self.assertTrue(provenance._check_mod_11_2("0000-0002-1694-233X"))

        # dashes optional
        self.assertTrue(provenance._check_mod_11_2("0000000218250097"))
        self.assertTrue(provenance._check_mod_11_2("0000000151093700"))
        self.assertTrue(provenance._check_mod_11_2("000000021694233X"))

        # Swap check-digits around to force error
        self.assertFalse(provenance._check_mod_11_2("0000-0002-1825-009X"))
        self.assertFalse(provenance._check_mod_11_2("0000-0001-5109-3707"))
        self.assertFalse(provenance._check_mod_11_2("0000-0002-1694-2330"))


    def test_valid_orcid(self):
        # https://orcid.org/ (Expected form)
        self.assertEqual(provenance._valid_orcid("https://orcid.org/0000-0002-1694-233X"), "https://orcid.org/0000-0002-1694-233X")

        # http://orcid.org
        self.assertEqual(provenance._valid_orcid("http://orcid.org/0000-0002-1694-233X"), "https://orcid.org/0000-0002-1694-233X")
        # orcid.org
        self.assertEqual(provenance._valid_orcid("orcid.org/0000-0001-5109-3700"), "https://orcid.org/0000-0001-5109-3700")
        # just the number
        self.assertEqual(provenance._valid_orcid("0000-0002-1825-0097"), "https://orcid.org/0000-0002-1825-0097")
        # ..but missing digit fails (even if checksum is correct)
        self.assertTrue(provenance._check_mod_11_2("0002-1694-233X"))
        with self.assertRaises(ValueError):
            provenance._valid_orcid("0002-1694-2332")

        # lower-case X is OK (and fixed)
        self.assertEqual(provenance._valid_orcid("https://orcid.org/0000-0002-1694-233x"), "https://orcid.org/0000-0002-1694-233X")
        # upper-case ORCID.ORG is OK.. (and fixed)
        self.assertEqual(provenance._valid_orcid("https://ORCID.ORG/0000-0002-1694-233X"), "https://orcid.org/0000-0002-1694-233X")
        # Unicode string (Python 2)
        self.assertEqual(provenance._valid_orcid(u"https://orcid.org/0000-0002-1694-233X"), "https://orcid.org/0000-0002-1694-233X")

    def test_invalid_orcid(self):
        # Wrong checkdigit fails
        with self.assertRaises(ValueError):
            provenance._valid_orcid("https://orcid.org/0000-0002-1694-2332")
        with self.assertRaises(ValueError):
            provenance._valid_orcid("0000-0002-1694-2332")

        # Missing dashes fails (although that's OK for checksum)
        with self.assertRaises(ValueError):
            provenance._valid_orcid("https://orcid.org/000000021694233X")
        with self.assertRaises(ValueError):
            provenance._valid_orcid("000000021694233X")
        # Wrong hostname fails
        with self.assertRaises(ValueError):
            provenance._valid_orcid("https://example.org/0000-0002-1694-233X")
        # Wrong protocol fails
        with self.assertRaises(ValueError):
            provenance._valid_orcid("ftp://orcid.org/0000-0002-1694-233X")
        # Trying to be clever fails (no URL parsing!)
        with self.assertRaises(ValueError):
            provenance._valid_orcid("https://orcid.org:443/0000-0002-1694-233X")
        with self.assertRaises(ValueError):
            provenance._valid_orcid("http://orcid.org:80/0000-0002-1694-233X")


class TestResearchObject(unittest.TestCase):
    # TODO: Test ResearchObject methods
    pass