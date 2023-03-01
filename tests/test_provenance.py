import json
import os
import pickle
import sys
import urllib
from pathlib import Path
from typing import IO, Any, Generator, cast

import arcp
import bagit
import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import DC, DCTERMS, RDF
from rdflib.term import Literal

from cwltool import provenance, provenance_constants
from cwltool.main import main
from cwltool.provenance import ResearchObject
from cwltool.stdfsaccess import StdFsAccess

from .util import get_data, needs_docker, working_directory

# RDF namespaces we'll query for later
ORE = Namespace("http://www.openarchives.org/ore/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
RO = Namespace("http://purl.org/wf4ever/ro#")
WFDESC = Namespace("http://purl.org/wf4ever/wfdesc#")
WFPROV = Namespace("http://purl.org/wf4ever/wfprov#")
SCHEMA = Namespace("http://schema.org/")
CWLPROV = Namespace("https://w3id.org/cwl/prov#")
OA = Namespace("http://www.w3.org/ns/oa#")


def cwltool(tmp_path: Path, *args: Any) -> Path:
    prov_folder = tmp_path / "provenance"
    prov_folder.mkdir()
    new_args = ["--provenance", str(prov_folder)]
    new_args.extend(args)
    # Run within a temporary directory to not pollute git checkout
    tmp_dir = tmp_path / "cwltool-run"
    tmp_dir.mkdir()
    with working_directory(tmp_dir):
        status = main(new_args)
        assert status == 0, f"Failed: cwltool.main({args})"
    return prov_folder


@needs_docker
def test_hello_workflow(tmp_path: Path) -> None:
    check_provenance(
        cwltool(
            tmp_path,
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "Hello workflow",
        )
    )


@needs_docker
def test_hello_single_tool(tmp_path: Path) -> None:
    check_provenance(
        cwltool(
            tmp_path,
            get_data("tests/wf/hello_single_tool.cwl"),
            "--message",
            "Hello tool",
        ),
        single_tool=True,
    )


@needs_docker
def test_revsort_workflow(tmp_path: Path) -> None:
    folder = cwltool(
        tmp_path,
        get_data("tests/wf/revsort.cwl"),
        get_data("tests/wf/revsort-job.json"),
    )
    check_output_object(folder)
    check_provenance(folder)


@needs_docker
def test_nested_workflow(tmp_path: Path) -> None:
    check_provenance(cwltool(tmp_path, get_data("tests/wf/nested.cwl")), nested=True)


@needs_docker
def test_secondary_files_implicit(tmp_path: Path) -> None:
    file1 = tmp_path / "foo1.txt"
    file1idx = tmp_path / "foo1.txt.idx"

    with open(str(file1), "w", encoding="ascii") as f:
        f.write("foo")
    with open(str(file1idx), "w", encoding="ascii") as f:
        f.write("bar")

    # secondary will be picked up by .idx
    folder = cwltool(tmp_path, get_data("tests/wf/sec-wf.cwl"), "--file1", str(file1))
    check_provenance(folder, secondary_files=True)
    check_secondary_files(folder)


@needs_docker
def test_secondary_files_explicit(tmp_path: Path) -> None:
    # Deliberately do NOT have common basename or extension
    file1dir = tmp_path / "foo"
    file1dir.mkdir()
    file1 = file1dir / "foo"
    file1idxdir = tmp_path / "bar"
    file1idxdir.mkdir()
    file1idx = file1idxdir / "bar"

    with open(file1, "w", encoding="ascii") as f:
        f.write("foo")
    with open(file1idx, "w", encoding="ascii") as f:
        f.write("bar")

    # explicit secondaryFiles
    job = {
        "file1": {
            "class": "File",
            "path": str(file1),
            "basename": "foo1.txt",
            "secondaryFiles": [
                {
                    "class": "File",
                    "path": str(file1idx),
                    "basename": "foo1.txt.idx",
                }
            ],
        }
    }

    jobJson = tmp_path / "job.json"
    with open(jobJson, "wb") as fp:
        j = json.dumps(job, ensure_ascii=True)
        fp.write(j.encode("ascii"))

    folder = cwltool(tmp_path, get_data("tests/wf/sec-wf.cwl"), str(jobJson))
    check_provenance(folder, secondary_files=True)
    check_secondary_files(folder)


@needs_docker
def test_secondary_files_output(tmp_path: Path) -> None:
    # secondary will be picked up by .idx
    folder = cwltool(tmp_path, get_data("tests/wf/sec-wf-out.cwl"))
    check_provenance(folder, secondary_files=True)
    # Skipped, not the same secondary files as above
    # self.check_secondary_files()


@needs_docker
def test_directory_workflow(tmp_path: Path) -> None:
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    sha1 = {
        # Expected hashes of ASCII letters (no linefeed)
        # as returned from:
        # for x in a b c ; do echo -n $x | sha1sum ; done
        "a": "86f7e437faa5a7fce15d1ddcb9eaeaea377667b8",
        "b": "e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98",
        "c": "84a516841ba77a5b4648de2cd0dfcb30ea46dbb4",
    }
    for x in "abc":
        # Make test files with predictable hashes
        with open(dir2 / x, "w", encoding="ascii") as f:
            f.write(x)

    folder = cwltool(tmp_path, get_data("tests/wf/directory.cwl"), "--dir", str(dir2))
    check_provenance(folder, directory=True)

    # Output should include ls stdout of filenames a b c on each line
    file_list = (
        folder
        / "data"
        / "3c"
        / "3ca69e8d6c234a469d16ac28a4a658c92267c423"
        # checksum as returned from:
        # echo -e "a\nb\nc" | sha1sum
        # 3ca69e8d6c234a469d16ac28a4a658c92267c423  -
    )
    assert file_list.is_file()

    # Input files should be captured by hash value,
    # even if they were inside a class: Directory
    for letter, l_hash in sha1.items():
        prefix = l_hash[:2]  # first 2 letters
        p = folder / "data" / prefix / l_hash
        assert p.is_file(), f"Could not find {letter} as {p}"


@needs_docker
def test_no_data_files(tmp_path: Path) -> None:
    folder = cwltool(
        tmp_path,
        get_data("tests/wf/conditional_step_no_inputs.cwl"),
    )
    check_bagit(folder)


def check_output_object(base_path: Path) -> None:
    output_obj = base_path / "workflow" / "primary-output.json"
    compare_checksum = "sha1$b9214658cc453331b62c2282b772a5c063dbd284"
    compare_location = "../data/b9/b9214658cc453331b62c2282b772a5c063dbd284"
    with open(output_obj) as fp:
        out_json = json.load(fp)
    f1 = out_json["sorted_output"]
    assert f1["checksum"] == compare_checksum
    assert f1["location"] == compare_location


def check_secondary_files(base_path: Path) -> None:
    foo_data = (
        base_path
        / "data"
        / "0b"
        / "0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33"
        # checksum as returned from:
        # $ echo -n foo | sha1sum
        # 0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33  -
    )
    bar_data = base_path / "data" / "62" / "62cdb7020ff920e5aa642c3d4066950dd1f01f4d"
    assert foo_data.is_file(), "Did not capture file.txt 'foo'"
    assert bar_data.is_file(), "Did not capture secondary file.txt.idx 'bar"

    primary_job = base_path / "workflow" / "primary-job.json"
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


def check_provenance(
    base_path: Path,
    nested: bool = False,
    single_tool: bool = False,
    directory: bool = False,
    secondary_files: bool = False,
) -> None:
    check_folders(base_path)
    check_bagit(base_path)
    check_ro(base_path, nested=nested)
    check_prov(
        base_path,
        nested=nested,
        single_tool=single_tool,
        directory=directory,
        secondary_files=secondary_files,
    )


def check_folders(base_path: Path) -> None:
    required_folders = [
        "data",
        "snapshot",
        "workflow",
        "metadata",
        os.path.join("metadata", "provenance"),
    ]

    for folder in required_folders:
        assert (base_path / folder).is_dir()


def check_bagit(base_path: Path) -> None:
    # check bagit structure
    required_files = [
        "bagit.txt",
        "bag-info.txt",
        "manifest-sha1.txt",
        "tagmanifest-sha1.txt",
        "tagmanifest-sha256.txt",
    ]

    for basename in required_files:
        assert (base_path / basename).is_file()

    bag = bagit.Bag(str(base_path))
    assert bag.has_oxum()
    (only_manifest, only_fs) = bag.compare_manifests_with_fs()
    assert not list(only_manifest), "Some files only in manifest"
    assert not list(only_fs), "Some files only on file system"
    missing_tagfiles = bag.missing_optional_tagfiles()
    assert not list(missing_tagfiles), "Some files only in tagmanifest"
    bag.validate()
    # TODO: Check other bag-info attributes
    assert arcp.is_arcp_uri(cast(str, bag.info.get("External-Identifier")))


def find_arcp(base_path: Path) -> str:
    # First try to find External-Identifier
    bag = bagit.Bag(str(base_path))
    ext_id = cast(str, bag.info.get("External-Identifier"))
    if arcp.is_arcp_uri(ext_id):
        return ext_id
    raise Exception("Can't find External-Identifier")


def _arcp2file(base_path: Path, uri: str) -> Path:
    parsed = arcp.parse_arcp(uri)
    # arcp URIs, ensure they are local to our RO
    assert (
        parsed.uuid == arcp.parse_arcp(find_arcp(base_path)).uuid
    ), "arcp URI must be local to the research object"

    path = parsed.path[1:]  # Strip first /
    return base_path / Path(path)


def check_ro(base_path: Path, nested: bool = False) -> None:
    manifest_file = base_path / "metadata" / "manifest.json"
    assert manifest_file.is_file(), f"Can't find {manifest_file}"
    arcp_root = find_arcp(base_path)
    base = urllib.parse.urljoin(arcp_root, "metadata/manifest.json")
    g = Graph()

    # Avoid resolving JSON-LD context https://w3id.org/bundle/context
    # so this test works offline
    context = Path(get_data("tests/bundle-context.jsonld")).as_uri()
    with open(manifest_file, encoding="UTF-8") as fh:
        jsonld = fh.read()
        # replace with file:/// URI
        jsonld = jsonld.replace("https://w3id.org/bundle/context", context)
    g.parse(data=jsonld, format="json-ld", publicID=base)
    if os.environ.get("DEBUG"):
        print("Parsed manifest:\n\n")
        g.serialize(cast(IO[bytes], sys.stdout), format="ttl")
    _ro = None

    for _ro in g.subjects(ORE.isDescribedBy, URIRef(base)):
        break
    assert _ro is not None, "Can't find RO with ore:isDescribedBy"

    profile = None
    for dc in g.objects(_ro, DCTERMS.conformsTo):
        profile = dc
        break
    assert profile is not None, "Can't find profile with dct:conformsTo"
    assert profile == URIRef(
        provenance_constants.CWLPROV_VERSION
    ), f"Unexpected cwlprov version {profile}"

    paths = []
    externals = []
    for aggregate in g.objects(_ro, ORE.aggregates):
        if not arcp.is_arcp_uri(cast(str, aggregate)):
            externals.append(aggregate)
            # Won't check external URIs existence here
            # TODO: Check they are not relative!
            continue
        lfile = _arcp2file(base_path, cast(str, aggregate))
        paths.append(os.path.relpath(lfile, base_path))
        assert os.path.isfile(lfile), f"Can't find aggregated {lfile}"

    assert paths, "Didn't find any arcp aggregates"
    assert externals, "Didn't find any data URIs"

    for ext in ["provn", "xml", "json", "jsonld", "nt", "ttl"]:
        f = "metadata/provenance/primary.cwlprov.%s" % ext
        assert f in paths, "provenance file missing " + f

    for f in [
        "workflow/primary-job.json",
        "workflow/packed.cwl",
        "workflow/primary-output.json",
    ]:
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
    for link in linked:
        assert (link, OA.hasBody, URIRef(packed)) in g
        assert (link, OA.hasBody, URIRef(primary_job)) in g
        assert (link, OA.hasTarget, URIRef(uuid.urn)) in g

    has_provenance = set(g.subjects(OA.hasBody, URIRef(primary_prov_nt)))
    for p in has_provenance:
        assert (p, OA.hasTarget, URIRef(uuid.urn)) in g
        assert (p, OA.motivatedBy, PROV.has_provenance) in g
        # Check all prov elements are listed
        formats = set()
        for prov in g.objects(p, OA.hasBody):
            assert (
                prov,
                DCTERMS.conformsTo,
                URIRef(provenance_constants.CWLPROV_VERSION),
            ) in g
            # NOTE: DC.format is a Namespace method and does not resolve like other terms
            formats.update(set(g.objects(prov, DC["format"])))
        assert formats, "Could not find media types"
        expected = {
            Literal(f)
            for f in (
                "application/json",
                "application/ld+json",
                "application/n-triples",
                'text/provenance-notation; charset="UTF-8"',
                'text/turtle; charset="UTF-8"',
                "application/xml",
            )
        }
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


def check_prov(
    base_path: Path,
    nested: bool = False,
    single_tool: bool = False,
    directory: bool = False,
    secondary_files: bool = False,
) -> None:
    prov_file = base_path / "metadata" / "provenance" / "primary.cwlprov.nt"
    assert prov_file.is_file(), f"Can't find {prov_file}"
    arcp_root = find_arcp(base_path)
    # Note: We don't need to include metadata/provnance in base URI
    # as .nt always use absolute URIs
    g = Graph()
    with open(prov_file, "rb") as f:
        g.parse(file=f, format="nt", publicID=arcp_root)
    if os.environ.get("DEBUG"):
        print("Parsed %s:\n\n" % prov_file)
        g.serialize(cast(IO[bytes], sys.stdout), format="ttl")
    runs = set(g.subjects(RDF.type, WFPROV.WorkflowRun))

    # main workflow run URI (as urn:uuid:) should correspond to arcp uuid part
    uuid = arcp.parse_arcp(arcp_root).uuid
    main_run = URIRef(uuid.urn)
    assert main_run in runs, f"Can't find run {main_run} in {runs}"
    # TODO: we should not need to parse arcp, but follow
    # the has_provenance annotations in manifest.json instead

    # run should have been started by a wf engine

    engines = set(g.subjects(RDF.type, WFPROV.WorkflowEngine))
    assert engines, "Could not find WorkflowEngine"
    assert len(engines) == 1, "Found too many WorkflowEngines: %s" % engines
    engine = engines.pop()

    assert (
        main_run,
        PROV.wasAssociatedWith,
        engine,
    ) in g, "Wf run not associated with wf engine"
    assert (
        engine,
        RDF.type,
        PROV.SoftwareAgent,
    ) in g, "Engine not declared as SoftwareAgent"

    if single_tool:
        activities = set(g.subjects(RDF.type, PROV.Activity))
        assert len(activities) == 1, "Too many activities: %s" % activities
        # single tool exec, there should be no other activities
        # than the tool run
        # (NOTE: the WorkflowEngine is also activity, but not declared explicitly)
    else:
        # Check all process runs were started by the main worklow
        stepActivities = set(g.subjects(RDF.type, WFPROV.ProcessRun))
        # Although semantically a WorkflowEngine is also a ProcessRun,
        # we don't declare that,
        # thus only the step activities should be in this set.
        assert main_run not in stepActivities
        assert stepActivities, "No steps executed in workflow"
        for step in stepActivities:
            # Let's check it was started by the main_run. Unfortunately, unlike PROV-N
            # in PROV-O RDF we have to check through the n-ary qualifiedStart relation
            starts = set(g.objects(step, PROV.qualifiedStart))
            assert starts, "Could not find qualifiedStart of step %s" % step
            assert len(starts) == 1, "Too many qualifiedStart for step %s" % step
            start = starts.pop()
            assert (
                start,
                PROV.hadActivity,
                main_run,
            ) in g, "Step activity not started by main activity"
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
            assert (d, RDF.type, PROV.Entity) in g
            assert len(list(g.objects(d, CWLPROV.basename))) == 1

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
                ef = entities.pop()
                files.add(ef)
                assert (entry, ORE.proxyFor, ef) in g
                assert (ef, RDF.type, PROV.Entity) in g

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
            assert str(sec_basename) == f"{sec_nameroot}{sec_nameext}"
            # TODO: Check hash data file exist in RO

            # The primary entity should have the same, but different values
            assert set(g.objects(prim, PROV.specializationOf))
            prim_basename = set(g.objects(prim, CWLPROV.basename)).pop()
            prim_nameroot = set(g.objects(prim, CWLPROV.nameroot)).pop()
            prim_nameext = set(g.objects(prim, CWLPROV.nameext)).pop()
            assert str(prim_basename) == f"{prim_nameroot}{prim_nameext}"


@pytest.fixture
def research_object(tmp_path: Path) -> Generator[ResearchObject, None, None]:
    re_ob = ResearchObject(StdFsAccess(str(tmp_path / "ro")), temp_prefix_ro=str(tmp_path / "tmp"))
    yield re_ob
    re_ob.close()


def test_absolute_path_fails(research_object: ResearchObject) -> None:
    with pytest.raises(ValueError):
        research_object.write_bag_file("/absolute/path/fails")


def test_climboutfails(research_object: ResearchObject) -> None:
    with pytest.raises(ValueError):
        research_object.write_bag_file("../../outside-ro")


def test_writable_string(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("file.txt") as fh:
        assert fh.writable()
        fh.write("Hello\n")

    sha1 = os.path.join(research_object.folder, "tagmanifest-sha1.txt")
    assert os.path.isfile(sha1)

    with open(sha1, encoding="UTF-8") as sha_file:
        stripped_sha = sha_file.readline().strip()
    assert stripped_sha.endswith("file.txt")
    # stain@biggie:~/src/cwltool$ echo Hello | sha1sum
    # 1d229271928d3f9e2bb0375bd6ce5db6c6d348d9  -
    assert stripped_sha.startswith("1d229271928d3f9e2bb0375bd6ce5db6c6d348d9")

    sha256 = os.path.join(research_object.folder, "tagmanifest-sha256.txt")
    assert os.path.isfile(sha256)

    with open(sha256, encoding="UTF-8") as sha_file:
        stripped_sha = sha_file.readline().strip()

    assert stripped_sha.endswith("file.txt")
    # stain@biggie:~/src/cwltool$ echo Hello | sha256sum
    # 66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18  -
    assert stripped_sha.startswith(
        "66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18"
    )

    sha512 = os.path.join(research_object.folder, "tagmanifest-sha512.txt")
    assert os.path.isfile(sha512)


def test_writable_unicode_string(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("file.txt") as fh:
        assert fh.writable()
        fh.write("Here is a snowman: \u2603 \n")


def test_writable_bytes(research_object: ResearchObject) -> None:
    string = "Here is a snowman: \u2603 \n".encode()
    with research_object.write_bag_file("file.txt", encoding=None) as fh:
        fh.write(string)  # type: ignore


def test_data(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("data/file.txt") as fh:
        assert fh.writable()
        fh.write("Hello\n")

    # Because this is under data/ it should add to manifest
    # rather than tagmanifest
    sha1 = os.path.join(research_object.folder, "manifest-sha1.txt")
    assert os.path.isfile(sha1)
    with open(sha1, encoding="UTF-8") as fh2:
        stripped_sha = fh2.readline().strip()
        assert stripped_sha.endswith("data/file.txt")


def test_not_seekable(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("file.txt") as fh:
        assert not fh.seekable()
        with pytest.raises(OSError):
            fh.seek(0)


def test_not_readable(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("file.txt") as fh:
        assert not fh.readable()
        with pytest.raises(OSError):
            fh.read()


def test_truncate_fails(research_object: ResearchObject) -> None:
    with research_object.write_bag_file("file.txt") as fh:
        fh.write("Hello there")
        fh.truncate()  # OK as we're always at end
        # Will fail because the checksum can't rewind
        with pytest.raises(OSError):
            fh.truncate(0)


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
    ("0000-0002-1694-2330", False),
]


@pytest.mark.parametrize("mod11,valid", mod_validness)
def test_check_mod_11_2(mod11: str, valid: bool) -> None:
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
]


@pytest.mark.parametrize("orcid,expected", orcid_uris)
def test_valid_orcid(orcid: str, expected: str) -> None:
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
    "",
]


@pytest.mark.parametrize("orcid", invalid_orcids)
def test_invalid_orcid(orcid: str) -> None:
    with pytest.raises(ValueError):
        provenance._valid_orcid(orcid)


def test_whoami() -> None:
    username, fullname = provenance._whoami()
    assert username and isinstance(username, str)
    assert fullname and isinstance(fullname, str)


def test_research_object() -> None:
    # TODO: Test ResearchObject methods
    pass


def test_research_object_picklability(research_object: ResearchObject) -> None:
    """Research object may need to be pickled (for Toil)."""
    assert pickle.dumps(research_object) is not None
