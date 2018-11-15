import json
import ntpath
import os
import posixpath
import shutil
import sys
import tempfile
from io import open

from six.moves import urllib

import arcp
import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, RDF

import bagit
# Module to be tested
from cwltool import load_tool, provenance
from cwltool.main import main
from cwltool.resolver import Path

from .util import get_data, needs_docker, temp_dir, working_directory

# RDF namespaces we'll query for later
ORE = Namespace("http://www.openarchives.org/ore/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
RO = Namespace("http://purl.org/wf4ever/ro#")
WFDESC = Namespace("http://purl.org/wf4ever/wfdesc#")
WFPROV = Namespace("http://purl.org/wf4ever/wfprov#")
SCHEMA = Namespace("http://schema.org/")
CWLPROV = Namespace("https://w3id.org/cwl/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")


@pytest.fixture
def folder():
    directory = tempfile.mkdtemp("ro")
    if os.environ.get("DEBUG"):
        print("%s folder: %s" % (__loader__.fullname, folder))
    yield directory

    if not os.environ.get("DEBUG"):
        shutil.rmtree(directory)


def cwltool(folder, *args):
    load_tool.loaders = {}
    new_args = ['--no-container', '--provenance', folder]
    new_args.extend(args)
    # Run within a temporary directory to not pollute git checkout
    with temp_dir("cwltool-run") as tmp_dir:
        with working_directory(tmp_dir):
            status = main(new_args)
            assert status == 0, "Failed: cwltool.main(%r)" % (args)

@needs_docker
def test_hello_workflow(folder):
    cwltool(folder, get_data('tests/wf/hello-workflow.cwl'), "--usermessage", "Hello workflow")
    check_provenance(folder)

@needs_docker
def test_hello_single_tool(folder):
    cwltool(folder, get_data('tests/wf/hello_single_tool.cwl'), "--message", "Hello tool")
    check_provenance(folder, single_tool=True)

@needs_docker
def test_revsort_workflow(folder):
    cwltool(folder, get_data('tests/wf/revsort.cwl'), get_data('tests/wf/revsort-job.json'))
    check_output_object(folder)
    check_provenance(folder)

@needs_docker
def test_nested_workflow(folder):
    cwltool(folder, get_data('tests/wf/nested.cwl'))
    check_provenance(folder, nested=True)

@needs_docker
def test_secondary_files_implicit(folder):
    tmpdir = tempfile.mkdtemp("test_secondary_files_implicit")
    file1 = os.path.join(tmpdir, "foo1.txt")
    file1idx = os.path.join(tmpdir, "foo1.txt.idx")

    with open(file1, "w", encoding="ascii") as f:
        f.write(u"foo")
    with open(file1idx, "w", encoding="ascii") as f:
        f.write(u"bar")

    # secondary will be picked up by .idx
    cwltool(folder, get_data('tests/wf/sec-wf.cwl'), "--file1", file1)
    check_provenance(folder, secondary_files=True)
    check_secondary_files(folder)

@needs_docker
def test_secondary_files_explicit(folder):
    # Deliberately do NOT have common basename or extension
    file1 = tempfile.mktemp("foo")
    file1idx = tempfile.mktemp("bar")

    with open(file1, "w", encoding="ascii") as f:
        f.write(u"foo")
    with open(file1idx, "w", encoding="ascii") as f:
        f.write(u"bar")

    # explicit secondaryFiles
    job = {"file1":
           {"class": "File",
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

    cwltool(folder, get_data('tests/wf/sec-wf.cwl'), jobJson)
    check_provenance(folder, secondary_files=True)
    check_secondary_files(folder)

@needs_docker
def test_secondary_files_output(folder):
    # secondary will be picked up by .idx
    cwltool(folder, get_data('tests/wf/sec-wf-out.cwl'))
    check_provenance(folder, secondary_files=True)
    # Skipped, not the same secondary files as above
    #self.check_secondary_files()

@needs_docker
def test_directory_workflow(folder):
    dir2 = os.path.join(tempfile.mkdtemp("test_directory_workflow"), "dir2")
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

    cwltool(folder, get_data('tests/wf/directory.cwl'), "--dir", dir2)
    check_provenance(folder, directory=True)

    # Output should include ls stdout of filenames a b c on each line
    file_list = os.path.join(
        folder, "data",
        # checksum as returned from:
        ## echo -e "a\nb\nc" | sha1sum
        ## 3ca69e8d6c234a469d16ac28a4a658c92267c423  -
        "3c",
        "3ca69e8d6c234a469d16ac28a4a658c92267c423")
    assert os.path.isfile(file_list)

    # Input files should be captured by hash value,
    # even if they were inside a class: Directory
    for (l, l_hash) in sha1.items():
        prefix = l_hash[:2] # first 2 letters
        p = os.path.join(folder, "data", prefix, l_hash)
        assert os.path.isfile(p), "Could not find %s as %s" % (l, p)

def check_output_object(base_path):
    output_obj = os.path.join(base_path, "workflow", "primary-output.json")
    compare_checksum = "sha1$b9214658cc453331b62c2282b772a5c063dbd284"
    compare_location = "../data/b9/b9214658cc453331b62c2282b772a5c063dbd284"
    with open(output_obj) as fp:
        out_json = json.load(fp)
    f1 = out_json["sorted_output"]
    assert f1["checksum"] == compare_checksum
    assert f1["location"] == compare_location


def check_secondary_files(base_path):
    foo_data = os.path.join(
        base_path, "data",
        # checksum as returned from:
        # $ echo -n foo | sha1sum
        # 0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33  -
        "0b",
        "0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33")
    bar_data = os.path.join(
        base_path, "data", "62", "62cdb7020ff920e5aa642c3d4066950dd1f01f4d")
    assert os.path.isfile(foo_data), "Did not capture file.txt 'foo'"
    assert os.path.isfile(bar_data), "Did not capture secondary file.txt.idx 'bar"

    primary_job = os.path.join(base_path, "workflow", "primary-job.json")
    with open(primary_job) as fp:
        job_json = json.load(fp)
    # TODO: Verify secondaryFile in primary-job.json
    f1 = job_json["file1"]
    assert f1["location"] == "../data/0b/0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33"
    assert f1["basename"] == "foo1.txt"

    secondaries = f1["secondaryFiles"]
    assert secondaries
    f1idx = secondaries[0]
    assert f1idx["location"] == "../data/62/62cdb7020ff920e5aa642c3d4066950dd1f01f4d"
    assert f1idx["basename"], "foo1.txt.idx"

def check_provenance(base_path, nested=False, single_tool=False, directory=False,
                     secondary_files=False):
    check_folders(base_path)
    check_bagit(base_path)
    check_ro(base_path, nested=nested)
    check_prov(base_path, nested=nested, single_tool=single_tool, directory=directory,
               secondary_files=secondary_files)

def check_folders(base_path):
    required_folders = [
        "data", "snapshot", "workflow", "metadata", os.path.join("metadata", "provenance")]

    for folder in required_folders:
        assert os.path.isdir(os.path.join(base_path, folder))

def check_bagit(base_path):
    # check bagit structure
    required_files = [
        "bagit.txt", "bag-info.txt", "manifest-sha1.txt",
        "tagmanifest-sha1.txt", "tagmanifest-sha256.txt"]

    for basename in required_files:
        file_path = os.path.join(base_path, basename)
        assert os.path.isfile(file_path)

    bag = bagit.Bag(base_path)
    assert bag.has_oxum()
    (only_manifest, only_fs) = bag.compare_manifests_with_fs()
    assert not list(only_manifest), "Some files only in manifest"
    assert not list(only_fs), "Some files only on file system"
    missing_tagfiles = bag.missing_optional_tagfiles()
    assert not list(missing_tagfiles), "Some files only in tagmanifest"
    bag.validate()
    # TODO: Check other bag-info attributes
    assert arcp.is_arcp_uri(bag.info.get("External-Identifier"))

def find_arcp(base_path):
    # First try to find External-Identifier
    bag = bagit.Bag(base_path)
    ext_id = bag.info.get("External-Identifier")
    if arcp.is_arcp_uri(ext_id):
        return ext_id
    raise Exception("Can't find External-Identifier")

def _arcp2file(base_path, uri):
    parsed = arcp.parse_arcp(uri)
    # arcp URIs, ensure they are local to our RO
    assert parsed.uuid == arcp.parse_arcp(find_arcp(base_path)).uuid,\
    'arcp URI must be local to the research object'

    path = parsed.path[1:]  # Strip first /
    # Convert to local path, in case it uses \ on Windows
    lpath = provenance._convert_path(path, posixpath, os.path)
    return os.path.join(base_path, lpath)

def check_ro(base_path, nested=False):
    manifest_file = os.path.join(base_path, "metadata", "manifest.json")
    assert os.path.isfile(manifest_file), "Can't find " + manifest_file
    arcp_root = find_arcp(base_path)
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
    assert ro is not None, "Can't find RO with ore:isDescribedBy"

    profile = None
    for dc in g.objects(ro, DCTERMS.conformsTo):
        profile = dc
        break
    assert profile is not None, "Can't find profile with dct:conformsTo"
    assert profile == URIRef(provenance.CWLPROV_VERSION),\
        "Unexpected cwlprov version " + profile

    paths = []
    externals = []
    for aggregate in g.objects(ro, ORE.aggregates):
        if not arcp.is_arcp_uri(aggregate):
            externals.append(aggregate)
            # Won't check external URIs existence here
            # TODO: Check they are not relative!
            continue
        lfile = _arcp2file(base_path, aggregate)
        paths.append(os.path.relpath(lfile, base_path))
        assert os.path.isfile(lfile), "Can't find aggregated " + lfile

    assert paths, "Didn't find any arcp aggregates"
    assert externals, "Didn't find any data URIs"

    for ext in ["provn", "xml", "json", "jsonld", "nt", "ttl"]:
        f = "metadata/provenance/primary.cwlprov.%s" % ext
        assert f in paths, "provenance file missing " + f

    for f in ["workflow/primary-job.json", "workflow/packed.cwl", "workflow/primary-output.json"]:
        assert f in paths, "workflow file missing " + f
    # Can't test snapshot/ files directly as their name varies

    # TODO: check urn:hash::sha1 thingies
    # TODO: Check OA annotations

    packed = urllib.parse.urljoin(arcp_root, "/workflow/packed.cwl")
    primary_job = urllib.parse.urljoin(arcp_root, "/workflow/primary-job.json")
    primary_prov_nt = urllib.parse.urljoin(arcp_root, "/metadata/provenance/primary.cwlprov.nt")
    uuid = arcp.parse_arcp(arcp_root).uuid

    highlights = set(g.subjects(OA.motivatedBy, OA.highlighting))
    assert highlights, "Didn't find highlights"
    for h in highlights:
        assert (h, OA.hasTarget, URIRef(packed)) in g

    describes = set(g.subjects(OA.motivatedBy, OA.describing))
    for d in describes:
        assert (d, OA.hasBody, URIRef(arcp_root)) in g
        assert (d, OA.hasTarget, URIRef(uuid.urn)) in g

    linked = set(g.subjects(OA.motivatedBy, OA.linking))
    for l in linked:
        assert (l, OA.hasBody, URIRef(packed)) in g
        assert (l, OA.hasBody, URIRef(primary_job)) in g
        assert (l, OA.hasTarget, URIRef(uuid.urn)) in g

    has_provenance = set(g.subjects(OA.hasBody, URIRef(primary_prov_nt)))
    for p in has_provenance:
        assert (p, OA.hasTarget, URIRef(uuid.urn)) in g
        assert (p, OA.motivatedBy, PROV.has_provenance) in g
        # Check all prov elements are listed
        formats = set()
        for prov in g.objects(p, OA.hasBody):
            assert (prov, DCTERMS.conformsTo, URIRef(provenance.CWLPROV_VERSION)) in g
            # NOTE: DC.format is a Namespace method and does not resolve like other terms
            formats.update(set(g.objects(prov, DC["format"])))
        assert formats, "Could not find media types"
        expected = set(Literal(f) for f in (
            "application/json",
            "application/ld+json",
            "application/n-triples",
            'text/provenance-notation; charset="UTF-8"',
            'text/turtle; charset="UTF-8"',
            "application/xml"
        ))
        assert formats == expected, "Did not match expected PROV media types"

    if nested:
        # Check for additional PROVs
        # Let's try to find the other wf run ID
        otherRuns = set()
        for p in g.subjects(OA.motivatedBy, PROV.has_provenance):
            if (p, OA.hasTarget, URIRef(uuid.urn)) in g:
                continue
            otherRuns.update(set(g.objects(p, OA.hasTarget)))
        assert otherRuns, "Could not find nested workflow run prov annotations"

def check_prov(base_path, nested=False, single_tool=False, directory=False,
               secondary_files=False):
    prov_file = os.path.join(base_path, "metadata", "provenance", "primary.cwlprov.nt")
    assert os.path.isfile(prov_file), "Can't find " + prov_file
    arcp_root = find_arcp(base_path)
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
    assert master_run in runs, "Can't find run %s in %s" % (master_run, runs)
    # TODO: we should not need to parse arcp, but follow
    # the has_provenance annotations in manifest.json instead

    # run should have been started by a wf engine

    engines = set(g.subjects(RDF.type, WFPROV.WorkflowEngine))
    assert engines, "Could not find WorkflowEngine"
    assert len(engines) == 1, "Found too many WorkflowEngines: %s" % engines
    engine = engines.pop()

    assert (master_run, PROV.wasAssociatedWith, engine) in g, "Wf run not associated with wf engine"
    assert (engine, RDF.type, PROV.SoftwareAgent) in g, "Engine not declared as SoftwareAgent"

    if single_tool:
        activities = set(g.subjects(RDF.type, PROV.Activity))
        assert len(activities) == 1, "Too many activities: %s" % activities
        # single tool exec, there should be no other activities
        # than the tool run
        # (NOTE: the WorkflowEngine is also activity, but not declared explicitly)
    else:
        # Check all process runs were started by the master worklow
        stepActivities = set(g.subjects(RDF.type, WFPROV.ProcessRun))
        # Although semantically a WorkflowEngine is also a ProcessRun,
        # we don't declare that,
        # thus only the step activities should be in this set.
        assert master_run not in stepActivities
        assert stepActivities, "No steps executed in workflow"
        for step in stepActivities:
            # Let's check it was started by the master_run. Unfortunately, unlike PROV-N
            # in PROV-O RDF we have to check through the n-ary qualifiedStart relation
            starts = set(g.objects(step, PROV.qualifiedStart))
            assert starts, "Could not find qualifiedStart of step %s" % step
            assert len(starts) == 1, "Too many qualifiedStart for step %s" % step
            start = starts.pop()
            assert (start, PROV.hadActivity, master_run) in g,\
                "Step activity not started by master activity"
            # Tip: Any nested workflow step executions should not be in this prov file,
            # but in separate file
    if nested:
        # Find some cwlprov.nt the nested workflow is described in
        prov_ids = set(g.objects(predicate=PROV.has_provenance))
        # FIXME: The above is a bit naive and does not check the subject is
        # one of the steps -- OK for now as this is the only case of prov:has_provenance
        assert prov_ids, "Could not find prov:has_provenance from nested workflow"

        nt_uris = [uri for uri in prov_ids if uri.endswith("cwlprov.nt")]
        # TODO: Look up manifest conformsTo and content-type rather than assuming magic filename
        assert nt_uris, "Could not find *.cwlprov.nt"
        # Load into new graph
        g2 = Graph()
        nt_uri = nt_uris.pop()
        with open(_arcp2file(base_path, nt_uri), "rb") as f:
            g2.parse(file=f, format="nt", publicID=nt_uri)
        # TODO: Check g2 statements that it's the same UUID activity inside
        # as in the outer step
    if directory:
        directories = set(g.subjects(RDF.type, RO.Folder))
        assert directories

        for d in directories:
            assert (d, RDF.type, PROV.Dictionary) in g
            assert (d, RDF.type, PROV.Collection) in g
            assert(d, RDF.type, PROV.Entity) in g

            files = set()
            for entry in g.objects(d, PROV.hadDictionaryMember):
                assert (entry, RDF.type, PROV.KeyEntityPair) in g
                # We don't check what that filename is here
                assert set(g.objects(entry, PROV.pairKey))

                # RO:Folder aspect
                assert set(g.objects(entry, RO.entryName))
                assert (d, ORE.aggregates, entry) in g
                assert (entry, RDF.type, RO.FolderEntry) in g
                assert (entry, RDF.type, ORE.Proxy) in g
                assert (entry, ORE.proxyIn, d) in g
                assert (entry, ORE.proxyIn, d) in g

                # Which file?
                entities = set(g.objects(entry, PROV.pairEntity))
                assert entities
                f = entities.pop()
                files.add(f)
                assert (entry, ORE.proxyFor, f) in g
                assert (f, RDF.type, PROV.Entity) in g

            if not files:
                assert (d, RDF.type, PROV.EmptyCollection) in g
                assert (d, RDF.type, PROV.EmptyDictionary) in g
    if secondary_files:
        derivations = set(g.subjects(RDF.type, CWLPROV.SecondaryFile))
        assert derivations
        for der in derivations:
            sec = set(g.subjects(PROV.qualifiedDerivation, der)).pop()
            prim = set(g.objects(der, PROV.entity)).pop()

            # UUID specializes a hash checksum
            assert set(g.objects(sec, PROV.specializationOf))
            # extensions etc.
            sec_basename = set(g.objects(sec, CWLPROV.basename)).pop()
            sec_nameroot = set(g.objects(sec, CWLPROV.nameroot)).pop()
            sec_nameext = set(g.objects(sec, CWLPROV.nameext)).pop()
            assert str(sec_basename) == "%s%s" % (sec_nameroot, sec_nameext)
            # TODO: Check hash data file exist in RO

            # The primary entity should have the same, but different values
            assert set(g.objects(prim, PROV.specializationOf))
            prim_basename = set(g.objects(prim, CWLPROV.basename)).pop()
            prim_nameroot = set(g.objects(prim, CWLPROV.nameroot)).pop()
            prim_nameext = set(g.objects(prim, CWLPROV.nameext)).pop()
            assert str(prim_basename) == "%s%s" % (prim_nameroot, prim_nameext)


valid_path_conversions = [
    ('a\\b\\c', ntpath, posixpath, 'a/b/c'),
    ('a/b/c', posixpath, ntpath, 'a\\b\\c'),
    ('a/b/c', posixpath, posixpath, 'a/b/c'),
    ('a\\b\\c', posixpath, ntpath, 'a\\b\\c')
]

@pytest.mark.parametrize('path,from_type,to_type,expected', valid_path_conversions)
def test_path_conversion(path, expected, from_type, to_type):
    assert provenance._convert_path(path, from_type, to_type) == expected

invalid_path_conversions = [
    ('/absolute/path', posixpath, ntpath),
    ('D:\\absolute\\path', ntpath, posixpath)
]

@pytest.mark.parametrize('path,from_type,to_type', invalid_path_conversions)
def test_failing_path_conversion(path, from_type, to_type):
    with pytest.raises(ValueError):
        provenance._convert_path(path, from_type, to_type)

@pytest.fixture
def research_object():
    re_ob = provenance.ResearchObject()
    yield re_ob
    re_ob.close()

def test_absolute_path_fails(research_object):
    with pytest.raises(ValueError):
        research_object.write_bag_file("/absolute/path/fails")

def test_climboutfails(research_object):
    with pytest.raises(ValueError):
        research_object.write_bag_file("../../outside-ro")

def test_writable_string(research_object):
    with research_object.write_bag_file("file.txt") as file:
        assert file.writable()
        file.write(u"Hello\n")
        # TODO: Check Windows does not modify \n to \r\n here

    sha1 = os.path.join(research_object.folder, "tagmanifest-sha1.txt")
    assert os.path.isfile(sha1)

    with open(sha1, "r", encoding="UTF-8") as sha_file:
        stripped_sha = sha_file.readline().strip()
    assert stripped_sha.endswith("file.txt")
    #stain@biggie:~/src/cwltool$ echo Hello | sha1sum
    #1d229271928d3f9e2bb0375bd6ce5db6c6d348d9  -
    assert stripped_sha.startswith("1d229271928d3f9e2bb0375bd6ce5db6c6d348d9")

    sha256 = os.path.join(research_object.folder, "tagmanifest-sha256.txt")
    assert os.path.isfile(sha256)

    with open(sha256, "r", encoding="UTF-8") as sha_file:
        stripped_sha = sha_file.readline().strip()

    assert stripped_sha.endswith("file.txt")
    #stain@biggie:~/src/cwltool$ echo Hello | sha256sum
    #66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18  -
    assert stripped_sha.startswith("66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18")

    sha512 = os.path.join(research_object.folder, "tagmanifest-sha512.txt")
    assert os.path.isfile(sha512)

def test_writable_unicode_string(research_object):
    with research_object.write_bag_file("file.txt") as file:
        assert file.writable()
        file.write(u"Here is a snowman: \u2603 \n")

def test_writable_bytes(research_object):
    string = u"Here is a snowman: \u2603 \n".encode("UTF-8")
    with research_object.write_bag_file("file.txt", encoding=None) as file:
        file.write(string)

def test_data(research_object):
    with research_object.write_bag_file("data/file.txt") as file:
        assert file.writable()
        file.write(u"Hello\n")
    # TODO: Check Windows does not modify \n to \r\n here

    # Because this is under data/ it should add to manifest
    # rather than tagmanifest
    sha1 = os.path.join(research_object.folder, "manifest-sha1.txt")
    assert os.path.isfile(sha1)
    with open(sha1, "r", encoding="UTF-8") as file:
        stripped_sha = file.readline().strip()
        assert stripped_sha.endswith("data/file.txt")

def test_not_seekable(research_object):
    with research_object.write_bag_file("file.txt") as file:
        assert not file.seekable()
        with pytest.raises(IOError):
            file.seek(0)

def test_not_readable(research_object):
    with research_object.write_bag_file("file.txt") as file:
        assert not file.readable()
        with pytest.raises(IOError):
            file.read()

def test_truncate_fails(research_object):
    with research_object.write_bag_file("file.txt") as file:
        file.write(u"Hello there")
        file.truncate()  # OK as we're always at end
        # Will fail because the checksum can't rewind
        with pytest.raises(IOError):
            file.truncate(0)

mod_validness = [
    # Taken from "Some sample ORCID iDs" on
    # https://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier
    ("0000-0002-1825-0097", True),
    ("0000-0001-5109-3700", True),
    ("0000-0002-1694-233X", True),
    # dashes optional
    ("0000000218250097", True),
    ("0000000151093700", True),
    ("000000021694233X", True),
    # do not fail on missing digits
    ("0002-1694-233X", True),
    # Swap check-digits around to force error
    ("0000-0002-1825-009X", False),
    ("0000-0001-5109-3707", False),
    ("0000-0002-1694-2330", False)
]

@pytest.mark.parametrize('mod11,valid', mod_validness)
def test_check_mod_11_2(mod11, valid):
    assert provenance._check_mod_11_2(mod11) == valid

orcid_uris = [
    # https://orcid.org/ (Expected form)
    ("https://orcid.org/0000-0002-1694-233X", "https://orcid.org/0000-0002-1694-233X"),
    # orcid.org
    ("http://orcid.org/0000-0002-1694-233X", "https://orcid.org/0000-0002-1694-233X"),
    # just the number
    ("0000-0002-1825-0097", "https://orcid.org/0000-0002-1825-0097"),
    # lower-case X is OK (and fixed)
    ("https://orcid.org/0000-0002-1694-233x", "https://orcid.org/0000-0002-1694-233X"),
    # upper-case ORCID.ORG is OK.. (and fixed)
    ("https://ORCID.ORG/0000-0002-1694-233X", "https://orcid.org/0000-0002-1694-233X"),
    # Unicode string (Python 2)
    (u"https://orcid.org/0000-0002-1694-233X", "https://orcid.org/0000-0002-1694-233X")
]

@pytest.mark.parametrize('orcid,expected', orcid_uris)
def test_valid_orcid(orcid, expected):
    assert provenance._valid_orcid(orcid) == expected

invalid_orcids = [
    # missing digit fails (even if checksum is correct)
    "0002-1694-2332",
    # Wrong checkdigit fails
    "https://orcid.org/0000-0002-1694-2332",
    "0000-0002-1694-2332",
    # Missing dashes fails (although that's OK for checksum)
    "https://orcid.org/000000021694233X",
    "000000021694233X",
    # Wrong hostname fails
    "https://example.org/0000-0002-1694-233X",
    # Wrong protocol fails
    "ftp://orcid.org/0000-0002-1694-233X",
    # Trying to be clever fails (no URL parsing!)
    "https://orcid.org:443/0000-0002-1694-233X",
    "http://orcid.org:80/0000-0002-1694-233X",
    # Empty string is not really valid
    ""
]

@pytest.mark.parametrize('orcid', invalid_orcids)
def test_invalid_orcid(orcid):
    with pytest.raises(ValueError):
        provenance._valid_orcid(orcid)

def test_whoami():
    username, fullname = provenance._whoami()
    assert username and isinstance(username, str)
    assert fullname and isinstance(fullname, str)

def test_research_object():
    # TODO: Test ResearchObject methods
    pass
