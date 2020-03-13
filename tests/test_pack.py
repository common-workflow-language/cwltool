import json
import os
import tempfile
from functools import partial
from io import StringIO
from tempfile import NamedTemporaryFile

import pytest

import cwltool.pack
import cwltool.workflow
from cwltool import load_tool
from cwltool.context import LoadingContext
from cwltool.load_tool import fetch_document, resolve_and_validate_document
from cwltool.main import main, make_relative, print_pack
from cwltool.pathmapper import adjustDirObjs, adjustFileObjs
from cwltool.resolver import tool_resolver
from ruamel import yaml

from .util import get_data, needs_docker


def test_pack():
    loadingContext, workflowobj, uri = fetch_document(get_data("tests/wf/revsort.cwl"))

    with open(get_data("tests/wf/expect_packed.cwl")) as packed_file:
        expect_packed = yaml.safe_load(packed_file)

    packed = cwltool.pack.pack(loadingContext.loader, uri, loadingContext.metadata)
    adjustFileObjs(
        packed, partial(make_relative, os.path.abspath(get_data("tests/wf")))
    )
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    assert "$schemas" in packed
    assert len(packed["$schemas"]) == len(expect_packed["$schemas"])
    del packed["$schemas"]
    del expect_packed["$schemas"]

    assert packed == expect_packed


def test_pack_input_named_name():
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/trick_revsort.cwl")
    )
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    with open(get_data("tests/wf/expect_trick_packed.cwl")) as packed_file:
        expect_packed = yaml.round_trip_load(packed_file)

    packed = cwltool.pack.pack(loadingContext.loader, uri, loadingContext.metadata)
    adjustFileObjs(
        packed, partial(make_relative, os.path.abspath(get_data("tests/wf")))
    )
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    assert "$schemas" in packed
    assert len(packed["$schemas"]) == len(expect_packed["$schemas"])
    del packed["$schemas"]
    del expect_packed["$schemas"]

    assert packed == expect_packed


def test_pack_single_tool():
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/formattest.cwl")
    )
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    packed = cwltool.pack.pack(loadingContext.loader, uri, loadingContext.metadata)
    assert "$schemas" in packed


def test_pack_fragment():
    with open(get_data("tests/wf/scatter2_subwf.cwl")) as packed_file:
        expect_packed = yaml.safe_load(packed_file)

    loadingContext, workflowobj, uri = fetch_document(get_data("tests/wf/scatter2.cwl"))
    packed = cwltool.pack.pack(
        loadingContext.loader, uri + "#scatterstep/mysub", loadingContext.metadata
    )
    adjustFileObjs(
        packed, partial(make_relative, os.path.abspath(get_data("tests/wf")))
    )
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    assert json.dumps(packed, sort_keys=True, indent=2) == json.dumps(
        expect_packed, sort_keys=True, indent=2
    )


def test_pack_rewrites():
    rewrites = {}

    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/default-wf5.cwl")
    )
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    cwltool.pack.pack(
        loadingContext.loader, uri, loadingContext.metadata, rewrite_out=rewrites,
    )

    assert len(rewrites) == 6


cwl_missing_version_paths = [
    "tests/wf/hello_single_tool.cwl",
    "tests/wf/hello-workflow.cwl",
]


@pytest.mark.parametrize("cwl_path", cwl_missing_version_paths)
def test_pack_missing_cwlVersion(cwl_path):
    """Ensure the generated pack output is not missing the `cwlVersion` in case of single tool workflow and single step workflow."""
    # Testing single tool workflow
    loadingContext, workflowobj, uri = fetch_document(get_data(cwl_path))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed = json.loads(print_pack(loadingContext.loader, uri, loadingContext.metadata))

    assert packed["cwlVersion"] == "v1.0"


def test_pack_idempotence_tool():
    """Ensure that pack produces exactly the same document for an already packed CommandLineTool."""
    _pack_idempotently("tests/wf/hello_single_tool.cwl")


def test_pack_idempotence_workflow():
    """Ensure that pack produces exactly the same document for an already packed workflow."""
    _pack_idempotently("tests/wf/count-lines1-wf.cwl")


def _pack_idempotently(document):
    loadingContext, workflowobj, uri = fetch_document(get_data(document))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed_text = print_pack(loadingContext.loader, uri, loadingContext.metadata)
    packed = json.loads(packed_text)

    with NamedTemporaryFile() as tmp:
        tmp.write(packed_text.encode("utf-8"))
        tmp.flush()

        loadingContext, workflowobj, uri2 = fetch_document(tmp.name)
        loadingContext.do_update = False
        loadingContext, uri2 = resolve_and_validate_document(
            loadingContext, workflowobj, uri2
        )
        processobj = loadingContext.loader.resolve_ref(uri2)[0]

        # generate pack output dict
        packed_text = print_pack(loadingContext.loader, uri2, loadingContext.metadata)
        double_packed = json.loads(packed_text)

    assert uri != uri2
    assert packed == double_packed


cwl_to_run = [
    ("tests/wf/count-lines1-wf.cwl", "tests/wf/wc-job.json", False),
    ("tests/wf/formattest.cwl", "tests/wf/formattest-job.json", True),
]


@needs_docker
@pytest.mark.parametrize("wf_path,job_path,namespaced", cwl_to_run)
def test_packed_workflow_execution(wf_path, job_path, namespaced, tmpdir):
    loadingContext = LoadingContext()
    loadingContext.resolver = tool_resolver
    loadingContext, workflowobj, uri = fetch_document(get_data(wf_path), loadingContext)
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    processobj = loadingContext.loader.resolve_ref(uri)[0]
    packed = json.loads(print_pack(loadingContext.loader, uri, loadingContext.metadata))

    assert not namespaced or "$namespaces" in packed

    wf_packed_handle, wf_packed_path = tempfile.mkstemp()
    with open(wf_packed_path, "w") as temp_file:
        json.dump(packed, temp_file)

    normal_output = StringIO()
    packed_output = StringIO()

    normal_params = ["--outdir", str(tmpdir), get_data(wf_path), get_data(job_path)]
    packed_params = [
        "--outdir",
        str(tmpdir),
        "--debug",
        wf_packed_path,
        get_data(job_path),
    ]

    assert main(normal_params, stdout=normal_output) == 0
    assert main(packed_params, stdout=packed_output) == 0

    assert json.loads(packed_output.getvalue()) == json.loads(normal_output.getvalue())

    os.close(wf_packed_handle)
    os.remove(wf_packed_path)
