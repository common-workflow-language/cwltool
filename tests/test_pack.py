import json
from ruamel import yaml
import os
import tempfile
from functools import partial

from six import StringIO
import pytest

import cwltool.pack
import cwltool.workflow
from cwltool import load_tool
from cwltool.load_tool import fetch_document, resolve_and_validate_document
from cwltool.main import main, make_relative, print_pack
from cwltool.pathmapper import adjustDirObjs, adjustFileObjs
from cwltool.resolver import tool_resolver
from cwltool.context import LoadingContext

from .util import get_data, needs_docker


def test_pack():
    loadingContext, workflowobj, uri = fetch_document(get_data("tests/wf/revsort.cwl"))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    with open(get_data("tests/wf/expect_packed.cwl")) as packed_file:
        expect_packed = yaml.safe_load(packed_file)

    packed = cwltool.pack.pack(loadingContext.loader, processobj, uri, loadingContext.metadata)
    adjustFileObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    assert "$schemas" in packed
    assert len(packed["$schemas"]) == len(expect_packed["$schemas"])
    del packed["$schemas"]
    del expect_packed["$schemas"]

    assert packed == expect_packed


def test_pack_single_tool():
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/formattest.cwl"))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    packed = cwltool.pack.pack(loadingContext.loader, processobj, uri, loadingContext.metadata)
    assert "$schemas" in packed

def test_pack_rewrites():
    rewrites = {}

    loadingContext, workflowobj, uri = fetch_document(get_data("tests/wf/default-wf5.cwl"))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    cwltool.pack.pack(loadingContext.loader, processobj, uri, loadingContext.metadata, rewrite_out=rewrites)

    assert len(rewrites) == 6

cwl_missing_version_paths = [
    "tests/wf/hello_single_tool.cwl",
    "tests/wf/hello-workflow.cwl"
]

@pytest.mark.parametrize('cwl_path', cwl_missing_version_paths)
def test_pack_missing_cwlVersion(cwl_path):
    """Ensure the generated pack output is not missing the `cwlVersion` in case of single tool workflow and single step workflow."""
    # Testing single tool workflow
    loadingContext, workflowobj, uri = fetch_document(get_data(cwl_path))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed = json.loads(print_pack(loadingContext.loader, processobj, uri, loadingContext.metadata))

    assert packed["cwlVersion"] == 'v1.0'

def test_pack_idempotence_tool():
    """Ensure that pack produces exactly the same document for an already packed CommandLineTool."""
    _pack_idempotently("tests/wf/hello_single_tool.cwl")

def test_pack_idempotence_workflow():
    """Ensure that pack produces exactly the same document for an already packed workflow."""
    _pack_idempotently("tests/wf/count-lines1-wf.cwl")

def _pack_idempotently(document):
    loadingContext, workflowobj, uri = fetch_document(
        get_data(document))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed = json.loads(print_pack(loadingContext.loader, processobj, uri, loadingContext.metadata))

    loadingContext, workflowobj, uri2 = fetch_document(packed)
    loadingContext.do_update = False
    loadingContext, uri2 = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]
    double_packed = json.loads(print_pack(loadingContext.loader, processobj, uri2, loadingContext.metadata))
    assert packed == double_packed

cwl_to_run = [
    ("tests/wf/count-lines1-wf.cwl",
     "tests/wf/wc-job.json",
     False
     ),
    ("tests/wf/formattest.cwl",
     "tests/wf/formattest-job.json",
     True
     ),
]

@needs_docker
@pytest.mark.parametrize('wf_path,job_path,namespaced', cwl_to_run)
def test_packed_workflow_execution(wf_path, job_path, namespaced, tmpdir):
    loadingContext = LoadingContext()
    loadingContext.resolver = tool_resolver
    loadingContext, workflowobj, uri = fetch_document(
        get_data(wf_path), loadingContext)
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)
    processobj = loadingContext.loader.resolve_ref(uri)[0]
    packed = json.loads(print_pack(loadingContext.loader, processobj, uri, loadingContext.metadata))

    assert not namespaced or "$namespaces" in packed

    wf_packed_handle, wf_packed_path = tempfile.mkstemp()
    with open(wf_packed_path, 'w') as temp_file:
        json.dump(packed, temp_file)

    normal_output = StringIO()
    packed_output = StringIO()

    normal_params = ['--outdir', str(tmpdir), get_data(wf_path), get_data(job_path)]
    packed_params = ['--outdir', str(tmpdir), '--debug', wf_packed_path, get_data(job_path)]

    assert main(normal_params, stdout=normal_output) == 0
    assert main(packed_params, stdout=packed_output) == 0

    assert json.loads(packed_output.getvalue()) == json.loads(normal_output.getvalue())

    os.close(wf_packed_handle)
    os.remove(wf_packed_path)
