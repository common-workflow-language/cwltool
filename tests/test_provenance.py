from __future__ import absolute_import
import unittest
import sys

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
from six.moves import urllib
from rdflib import Namespace, URIRef, Graph
from rdflib.namespace import DCTERMS
import arcp


ORE=Namespace("http://www.openarchives.org/ore/terms/")

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
        self.check_provenance()

    def test_hello_single_tool(self):
        self.assertEquals(main(['--provenance', self.folder, get_data('tests/wf/hello_single_tool.cwl'),
            "--message", "Hello tool"]), 0)
        self.check_provenance()

    def test_revsort_workflow(self):
        self.assertEquals(main(['--no-container', '--provenance', self.folder, get_data('tests/wf/revsort.cwl'),
            get_data('tests/wf/revsort-job.json')]), 0)
        self.check_provenance()

    def check_provenance(self):
        self.check_folders()
        self.check_bagit()
        self.check_ro()

    def check_folders(self):
        # Our folders
        for d in ("data", "snapshot", "workflow", "metadata", os.path.join("metadata", "provenance")):
            f = os.path.join(self.folder, d)
            self.assertTrue(os.path.isdir(f))

    def check_bagit(self):
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
        # TODO: Check other bag-info attributes
        self.assertTrue(arcp.is_arcp_uri(bag.info.get("External-Identifier")))

    def find_arcp(self):
        # First try to find External-Identifier
        bag = bagit.Bag(self.folder)
        ext_id = bag.info.get("External-Identifier")
        if arcp.is_arcp_uri(ext_id):
            return ext_id
        else:
            return arcp.arcp_random()

    def check_ro(self):
        manifest_file = os.path.join(self.folder, "metadata", "manifest.json")
        self.assertTrue(os.path.isfile(manifest_file), "Can't find " + manifest_file)
        arcp_root = self.find_arcp()
        base = urllib.parse.urljoin(arcp_root, "metadata/manifest.json")
        g = Graph()
        with open(manifest_file, "rb") as f:
            # Note: This will use https://w3id.org/bundle/context
            g.parse(file=f, format="json-ld", publicID=base)
        print("Parsed manifest:\n\n")
        g.serialize(sys.stdout, format="nt")
        ro = None

        for ro in g.subjects(ORE.isDescribedBy, URIRef(base)):
            break
        self.assertTrue(ro, "Can't find RO with ore:isDescribedBy")

        profile = None
        for dc in g.objects(ro, DCTERMS.conformsTo):
            profile = dc
            break
        self.assertTrue(profile, "Can't find profile with dct:conformsTo")
        self.assertEquals(profile, URIRef("https://w3id.org/cwl/prov/0.3.0"),
            "Unexpected cwlprov version " + profile)

        paths = []
        externals = []
        for aggregate in g.objects(ro, ORE.aggregates):
            print(aggregate)
            if not arcp.is_arcp_uri(aggregate):
                externals.append(aggregate)
                # Won't check external URIs existence here
                # TODO: Check they are not relative!
                continue
            # arcp URIs - assume they are local to our RO
            path = arcp.parse_arcp(aggregate).path[1:]  # Strip first /
            paths.append(path)
            # Convert to local path, in case it uses \ on Windows
            lpath = provenance._convert_path(path, posixpath, os.path)
            lfile = os.path.join(self.folder, lpath)
            self.assertTrue(os.path.isfile(lfile), "Can't find aggregated " + lfile)

        self.assertTrue(paths, "Didn't find any arcp aggregates")
        self.assertTrue(externals, "Didn't find any data URIs")

        for ext in ["provn", "xml", "json", "jsonld", "nt", "ttl"]:
            f = "metadata/provenance/primary.cwlprov.%s" % ext
            self.assertTrue(f in paths, "provenance file missing " + f)

        for f in ["workflow/primary-job.json", "workflow/packed.cwl"]:
            self.assertTrue(f in paths, "workflow file missing " + f)
        # Can't test snapshot/ files directly as their name varies

        # TODO: check urn:hash::sha1 thingies
        # TODO: Check OA annotations


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
            f.truncate()  # OK as we're always at end
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
