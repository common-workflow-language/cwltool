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
from cwltool.resolver import Path

# Module to be tested
from cwltool import provenance
from cwltool import load_tool

from .util import get_data
import bagit
import posixpath
import ntpath
from six.moves import urllib
from rdflib import Namespace, URIRef, Graph, Literal
from rdflib.namespace import RDF,RDFS,SKOS,DCTERMS,FOAF,XSD,DC
import arcp
import json


# RDF namespaces we'll query for later
ORE = Namespace("http://www.openarchives.org/ore/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
RO = Namespace("http://purl.org/wf4ever/ro#")
WFDESC = Namespace("http://purl.org/wf4ever/wfdesc#")
WFPROV = Namespace("http://purl.org/wf4ever/wfprov#")
SCHEMA = Namespace("http://schema.org/")
CWLPROV = Namespace("https://w3id.org/cwl/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")


@pytest.mark.skipif(onWindows(),
                    reason="On Windows this would invoke a default docker container, some of the test workflows need unix commands")
class TestProvenance(unittest.TestCase):
    folder = None


    def cwltool(self, *args):
        load_tool.loaders = {}
        new_args = ['--no-container',
            '--provenance',
            self.folder]
        new_args.extend(args)
        # Run within a temporary directory to not pollute git checkout
        test_dir = os.path.abspath(os.curdir)
        tmp_dir = tempfile.mkdtemp("cwltool-run")
        os.chdir(tmp_dir)
        try:
            status = main(new_args)
            self.assertEquals(status, 0, "Failed: cwltool.main(%r)" % (args,))
        finally:
            # Change back
            os.chdir(test_dir)

    def setUp(self):
        self.folder = tempfile.mkdtemp("ro")
        if os.environ.get("DEBUG"):
            print("%s folder: %s" % (self, self.folder))

    def tearDown(self):
        if self.folder and not os.environ.get("DEBUG"):
            shutil.rmtree(self.folder)

    def test_hello_workflow(self):
        self.cwltool(get_data('tests/wf/hello-workflow.cwl'),
            "--usermessage", "Hello workflow")
        self.check_provenance()

    def test_hello_single_tool(self):
        self.cwltool(get_data('tests/wf/hello_single_tool.cwl'),
            "--message", "Hello tool")
        self.check_provenance(single_tool=True)

    def test_revsort_workflow(self):
        self.cwltool(get_data('tests/wf/revsort.cwl'),
            get_data('tests/wf/revsort-job.json'))
        self.check_provenance()

    def test_nested_workflow(self):
        self.cwltool(get_data('tests/wf/nested.cwl'))
        self.check_provenance(nested=True)

    def test_secondary_files_implicit(self):
        tmpdir = tempfile.mkdtemp("test_secondary_files_implicit")
        file1 = os.path.join(tmpdir, "foo1.txt")
        file1idx = os.path.join(tmpdir, "foo1.txt.idx")

        with open(file1, "w", encoding="ascii") as f:
            f.write(u"foo")
        with open(file1idx, "w", encoding="ascii") as f:
            f.write(u"bar")

        # secondary will be picked up by .idx
        self.cwltool(get_data('tests/wf/sec-wf.cwl'), "--file1", file1)
        self.check_provenance(secondary_files=True)
        self.check_secondary_files()

    def test_secondary_files_explicit(self):
        # Deliberately do NOT have common basename or extension
        file1 = tempfile.mktemp("foo")
        file1idx = tempfile.mktemp("bar")

        with open(file1, "w", encoding="ascii") as f:
            f.write(u"foo")
        with open(file1idx, "w", encoding="ascii") as f:
            f.write(u"bar")

        # explicit secondaryFiles
        job = {
            "file1":
                { "class": "File",
                    "path": file1,
                    "basename": "foo1.txt",
                    "secondaryFiles": [
                        {
                            "class": "File",
                            "path": file1idx,
                            "basename": "foo1.txt.idx",
                        }
                    ]
                }
        }
        jobJson = tempfile.mktemp("job.json")
        with open(jobJson, "wb") as fp:
            j = json.dumps(job, ensure_ascii=True)
            fp.write(j.encode("ascii"))

        self.cwltool(get_data('tests/wf/sec-wf.cwl'), jobJson)
        self.check_provenance(secondary_files=True)
        self.check_secondary_files()

    def test_secondary_files_output(self):
        # secondary will be picked up by .idx
        self.cwltool(get_data('tests/wf/sec-wf-out.cwl'))
        self.check_provenance(secondary_files=True)
        # Skipped, not the same secondary files as above
        #self.check_secondary_files()

    def test_directory_workflow(self):
        dir2 = os.path.join(tempfile.mkdtemp("test_directory_workflow"),
            "dir2")
        os.makedirs(dir2)
        sha1 = {
            # Expected hashes of ASCII letters (no linefeed)
            # as returned from:
            ## for x in a b c ; do echo -n $x | sha1sum ; done
            "a": "86f7e437faa5a7fce15d1ddcb9eaeaea377667b8",
            "b": "e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98",
            "c": "84a516841ba77a5b4648de2cd0dfcb30ea46dbb4",
        }
        for x in u"abc":
            # Make test files with predictable hashes
            with open(os.path.join(dir2, x), "w", encoding="ascii") as f:
                f.write(x)

        self.cwltool(get_data('tests/wf/directory.cwl'),
            "--dir", dir2)
        self.check_provenance(directory=True)

        # Output should include ls stdout of filenames a b c on each line
        ls = os.path.join(self.folder, "data",
            # checksum as returned from:
            ## echo -e "a\nb\nc" | sha1sum
            ## 3ca69e8d6c234a469d16ac28a4a658c92267c423  -
            "3c",
            "3ca69e8d6c234a469d16ac28a4a658c92267c423")
        self.assertTrue(os.path.isfile(ls))

        # Input files should be captured by hash value,
        # even if they were inside a class: Directory
        for (l,l_hash) in sha1.items():
            prefix = l_hash[:2] # first 2 letters
            p = os.path.join(self.folder, "data", prefix, l_hash)
            self.assertTrue(os.path.isfile(p),
                "Could not find %s as %s" % (l, p))

    def check_secondary_files(self):
        foo_data = os.path.join(self.folder, "data",
            # checksum as returned from:
            # $ echo -n foo | sha1sum
            # 0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33  -
            "0b",
            "0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33")
        bar_data = os.path.join(self.folder, "data", "62",
            "62cdb7020ff920e5aa642c3d4066950dd1f01f4d")
        self.assertTrue(os.path.isfile(foo_data),
            "Did not capture file.txt 'foo'")
        self.assertTrue(os.path.isfile(bar_data),
            "Did not capture secondary file.txt.idx 'bar")

        primary_job = os.path.join(self.folder, "workflow", "primary-job.json")
        with open(primary_job) as fp:
            job_json = json.load(fp)
        # TODO: Verify secondaryFile in primary-job.json
        f1 = job_json["file1"]
        self.assertEquals(f1["location"],
            "../data/0b/0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33")
        self.assertEquals(f1["basename"],
            "foo1.txt")

        secondaries = f1["secondaryFiles"]
        self.assertTrue(secondaries)
        f1idx = secondaries[0]
        self.assertEquals(f1idx["location"],
            "../data/62/62cdb7020ff920e5aa642c3d4066950dd1f01f4d")
        self.assertEquals(f1idx["basename"],
            "foo1.txt.idx")


    def check_provenance(self, nested=False, single_tool=False, directory=False,
                         secondary_files=False):
        self.check_folders()
        self.check_bagit()
        self.check_ro(nested=nested)
        self.check_prov(nested=nested, single_tool=single_tool, directory=directory,
                        secondary_files=secondary_files)

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
        raise Exception("Can't find External-Identifier")
        # return arcp.arcp_random()

    def _arcp2file(self, uri):
        parsed = arcp.parse_arcp(uri)
        # arcp URIs, ensure they are local to our RO
        self.assertEquals(parsed.uuid,
            arcp.parse_arcp(self.find_arcp()).uuid)

        path = parsed.path[1:]  # Strip first /
        # Convert to local path, in case it uses \ on Windows
        lpath = provenance._convert_path(path, posixpath, os.path)
        return os.path.join(self.folder, lpath)

    def check_ro(self, nested=False):
        manifest_file = os.path.join(self.folder, "metadata", "manifest.json")
        self.assertTrue(os.path.isfile(manifest_file), "Can't find " + manifest_file)
        arcp_root = self.find_arcp()
        base = urllib.parse.urljoin(arcp_root, "metadata/manifest.json")
        g = Graph()

        # Avoid resolving JSON-LD context https://w3id.org/bundle/context
        # so this test works offline
        context = Path(get_data("tests/bundle-context.jsonld")).as_uri()
        with open(manifest_file, "r", encoding="UTF-8") as f:
            jsonld = f.read()
            # replace with file:/// URI
            jsonld = jsonld.replace("https://w3id.org/bundle/context", context)
        g.parse(data=jsonld, format="json-ld", publicID=base)
        if os.environ.get("DEBUG"):
            print("Parsed manifest:\n\n")
            g.serialize(sys.stdout, format="ttl")
        ro = None

        for ro in g.subjects(ORE.isDescribedBy, URIRef(base)):
            break
        self.assertTrue(ro, "Can't find RO with ore:isDescribedBy")

        profile = None
        for dc in g.objects(ro, DCTERMS.conformsTo):
            profile = dc
            break
        self.assertTrue(profile, "Can't find profile with dct:conformsTo")
        self.assertEquals(profile, URIRef(provenance.CWLPROV_VERSION),
            "Unexpected cwlprov version " + profile)

        paths = []
        externals = []
        for aggregate in g.objects(ro, ORE.aggregates):
            if not arcp.is_arcp_uri(aggregate):
                externals.append(aggregate)
                # Won't check external URIs existence here
                # TODO: Check they are not relative!
                continue
            lfile = self._arcp2file(aggregate)
            paths.append(os.path.relpath(lfile, self.folder))
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

        packed = urllib.parse.urljoin(arcp_root, "/workflow/packed.cwl")
        primary_job = urllib.parse.urljoin(arcp_root, "/workflow/primary-job.json")
        primary_prov_nt = urllib.parse.urljoin(arcp_root, "/metadata/provenance/primary.cwlprov.nt")
        uuid = arcp.parse_arcp(arcp_root).uuid

        highlights = set(g.subjects(OA.motivatedBy, OA.highlighting))
        self.assertTrue(highlights, "Didn't find highlights")
        for h in highlights:
            self.assertTrue( (h, OA.hasTarget, URIRef(packed)) in g)

        describes = set(g.subjects(OA.motivatedBy, OA.describing))
        for d in describes:
            self.assertTrue( (d, OA.hasBody, URIRef(arcp_root)) in g)
            self.assertTrue( (d, OA.hasTarget, URIRef(uuid.urn)) in g)

        linked = set(g.subjects(OA.motivatedBy, OA.linking))
        for l in linked:
            self.assertTrue( (l, OA.hasBody, URIRef(packed)) in g)
            self.assertTrue( (l, OA.hasBody, URIRef(primary_job)) in g)
            self.assertTrue( (l, OA.hasTarget, URIRef(uuid.urn)) in g)

        has_provenance = set(g.subjects(OA.hasBody, URIRef(primary_prov_nt)))
        for p in has_provenance:
            self.assertTrue( (p, OA.hasTarget, URIRef(uuid.urn)) in g)
            self.assertTrue( (p, OA.motivatedBy, PROV.has_provenance) in g)
            # Check all prov elements are listed
            formats = set()
            for prov in g.objects(p,OA.hasBody):
                self.assertTrue( (prov, DCTERMS.conformsTo,
                                  URIRef(provenance.CWLPROV_VERSION) ) in g)
                # NOTE: DC.format is a Namespace method and does not resolve like other terms
                formats.update(set(g.objects(prov, DC["format"])))
            self.assertTrue(formats, "Could not find media types")
            expected = set(Literal(f) for f in (
                "application/json",
                "application/ld+json",
                "application/n-triples",
                'text/provenance-notation; charset="UTF-8"',
                'text/turtle; charset="UTF-8"',
                "application/xml"
            ))
            self.assertEquals(formats, expected,
                "Did not match expected PROV media types")

        if nested:
            # Check for additional PROVs
            # Let's try to find the other wf run ID
            otherRuns = set()
            for p in g.subjects(OA.motivatedBy, PROV.has_provenance):
                if (p, OA.hasTarget, URIRef(uuid.urn)) in g:
                    continue
                otherRuns.update(set(g.objects(p, OA.hasTarget)))
            self.assertTrue(otherRuns, "Could not find nested workflow run prov annotations")

    def check_prov(self, nested=False, single_tool=False, directory=False,
                   secondary_files=False):
        prov_file = os.path.join(self.folder, "metadata", "provenance", "primary.cwlprov.nt")
        self.assertTrue(os.path.isfile(prov_file), "Can't find " + prov_file)
        arcp_root = self.find_arcp()
        # Note: We don't need to include metadata/provnance in base URI
        # as .nt always use absolute URIs
        g = Graph()
        with open(prov_file, "rb") as f:
            g.parse(file=f, format="nt", publicID=arcp_root)
        if os.environ.get("DEBUG"):
            print("Parsed %s:\n\n" % prov_file)
            g.serialize(sys.stdout, format="ttl")
        runs = set(g.subjects(RDF.type, WFPROV.WorkflowRun))

        # master workflow run URI (as urn:uuid:) should correspond to arcp uuid part
        uuid = arcp.parse_arcp(arcp_root).uuid
        master_run = URIRef(uuid.urn)
        self.assertTrue(master_run in runs,
            "Can't find run %s in %s" % (master_run, runs))
        # TODO: we should not need to parse arcp, but follow
        # the has_provenance annotations in manifest.json instead

        # run should have been started by a wf engine

        engines = set(g.subjects(RDF.type, WFPROV.WorkflowEngine))
        self.assertTrue(engines, "Could not find WorkflowEngine")
        self.assertEquals(1, len(engines),
            "Found too many WorkflowEngines: %s" % engines)
        engine = engines.pop()

        self.assertTrue((master_run, PROV.wasAssociatedWith, engine) in g,
            "Wf run not associated with wf engine")
        self.assertTrue((engine, RDF.type, PROV.SoftwareAgent) in g,
            "Engine not declared as SoftwareAgent")

        if single_tool:
            activities = set(g.subjects(RDF.type, PROV.Activity))
            self.assertEquals(1, len(activities),
                "Too many activities: %s" % activities)
            # single tool exec, there should be no other activities
            # than the tool run
            # (NOTE: the WorkflowEngine is also activity, but not declared explicitly)
        else:
            # Check all process runs were started by the master worklow
            stepActivities = set(g.subjects(RDF.type, WFPROV.ProcessRun))
            # Although semantically a WorkflowEngine is also a ProcessRun,
            # we don't declare that,
            # thus only the step activities should be in this set.
            self.assertFalse(master_run in stepActivities)
            self.assertTrue(stepActivities, "No steps executed in workflow")
            for step in stepActivities:
                # Let's check it was started by the master_run. Unfortunately, unlike PROV-N
                # in PROV-O RDF we have to check through the n-ary qualifiedStart relation
                starts = set(g.objects(step, PROV.qualifiedStart))
                self.assertTrue(starts, "Could not find qualifiedStart of step %s" % step)
                self.assertEquals(1, len(starts),
                    "Too many qualifiedStart for step %s" % step)
                start = starts.pop()
                self.assertTrue((start, PROV.hadActivity, master_run) in g,
                    "Step activity not started by master activity")
                # Tip: Any nested workflow step executions should not be in this prov file,
                # but in separate file
        if nested:
            # Find some cwlprov.nt the nested workflow is described in
            prov_ids = set(g.objects(predicate=PROV.has_provenance))
            # FIXME: The above is a bit naive and does not check the subject is
            # one of the steps -- OK for now as this is the only case of prov:has_provenance
            self.assertTrue(prov_ids, "Could not find prov:has_provenance from nested workflow")

            nt_uris = [uri for uri in prov_ids if uri.endswith("cwlprov.nt")]
            # TODO: Look up manifest conformsTo and content-type rather than assuming magic filename
            self.assertTrue(nt_uris, "Could not find *.cwlprov.nt")
            # Load into new graph
            g2 = Graph()
            nt_uri = nt_uris.pop()
            with open(self._arcp2file(nt_uri), "rb") as f:
                g2.parse(file=f, format="nt", publicID=nt_uri)
            # TODO: Check g2 statements that it's the same UUID activity inside
            # as in the outer step
        if directory:
            directories = set(g.subjects(RDF.type, RO.Folder))
            self.assertTrue(directories)

            for d in directories:
                self.assertTrue((d,RDF.type,PROV.Dictionary) in g)
                self.assertTrue((d,RDF.type,PROV.Collection) in g)
                self.assertTrue((d,RDF.type,PROV.Entity) in g)

                files = set()
                for entry in g.objects(d, PROV.hadDictionaryMember):
                    self.assertTrue((entry,RDF.type,PROV.KeyEntityPair) in g)
                    # We don't check what that filename is here
                    self.assertTrue(set(g.objects(entry,PROV.pairKey)))

                    # RO:Folder aspect
                    self.assertTrue(set(g.objects(entry,RO.entryName)))
                    self.assertTrue((d,ORE.aggregates,entry) in g)
                    self.assertTrue((entry,RDF.type,RO.FolderEntry) in g)
                    self.assertTrue((entry,RDF.type,ORE.Proxy) in g)
                    self.assertTrue((entry,ORE.proxyIn,d) in g)
                    self.assertTrue((entry,ORE.proxyIn,d) in g)

                    # Which file?
                    entities = set(g.objects(entry, PROV.pairEntity))
                    self.assertTrue(entities)
                    f = entities.pop()
                    files.add(f)
                    self.assertTrue((entry,ORE.proxyFor,f) in g)
                    self.assertTrue((f,RDF.type,PROV.Entity) in g)

                if not files:
                    self.assertTrue((d,RDF.type,PROV.EmptyCollection) in g)
                    self.assertTrue((d,RDF.type,PROV.EmptyDictionary) in g)
        if secondary_files:
            derivations = set(g.subjects(RDF.type, CWLPROV.SecondaryFile))
            self.assertTrue(derivations)
            for der in derivations:
                sec = set(g.subjects(PROV.qualifiedDerivation, der)).pop()
                prim = set(g.objects(der, PROV.entity)).pop()

                # UUID specializes a hash checksum
                self.assertTrue(set(g.objects(sec, PROV.specializationOf)))
                # extensions etc.
                sec_basename = set(g.objects(sec, CWLPROV.basename)).pop()
                sec_nameroot = set(g.objects(sec, CWLPROV.nameroot)).pop()
                sec_nameext = set(g.objects(sec, CWLPROV.nameext)).pop()
                self.assertEquals(str(sec_basename), "%s%s" % (sec_nameroot, sec_nameext))
                # TODO: Check hash data file exist in RO

                # The primary entity should have the same, but different values
                self.assertTrue(set(g.objects(prim, PROV.specializationOf)))
                prim_basename = set(g.objects(prim, CWLPROV.basename)).pop()
                prim_nameroot = set(g.objects(prim, CWLPROV.nameroot)).pop()
                prim_nameext = set(g.objects(prim, CWLPROV.nameext)).pop()
                self.assertEquals(str(prim_basename), "%s%s" % (prim_nameroot, prim_nameext))


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
