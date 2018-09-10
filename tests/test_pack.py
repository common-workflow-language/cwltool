import json
import os
import tempfile
from functools import partial

from six import StringIO
import pytest

import cwltool.pack
import cwltool.workflow
from cwltool import load_tool
from cwltool.load_tool import fetch_document, validate_document
from cwltool.main import main, make_relative, print_pack
from cwltool.pathmapper import adjustDirObjs, adjustFileObjs
from cwltool.resolver import tool_resolver

from .util import get_data, needs_docker


def test_pack():
    load_tool.loaders = {}

    document_loader, workflowobj, uri = fetch_document(get_data("tests/wf/revsort.cwl"))
    document_loader, _, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri)

    with open(get_data("tests/wf/expect_packed.cwl")) as packed_file:
        expect_packed = json.load(packed_file)

    packed = cwltool.pack.pack(document_loader, processobj, uri, metadata)
    adjustFileObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    assert "$schemas" in packed

    del packed["$schemas"]
    del expect_packed["$schemas"]

    assert packed == expect_packed


def test_pack_rewrites():
    load_tool.loaders = {}
    rewrites = {}

    document_loader, workflowobj, uri = fetch_document(get_data("tests/wf/default-wf5.cwl"))
    document_loader, _, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri)

    cwltool.pack.pack(document_loader, processobj, uri, metadata, rewrite_out=rewrites)

    assert len(rewrites) == 6

cwl_missing_version_paths = [
    "tests/wf/hello_single_tool.cwl",
    "tests/wf/hello-workflow.cwl"
]

@pytest.mark.parametrize('cwl_path', cwl_missing_version_paths)
def test_pack_missing_cwlVersion(cwl_path):
    """Test to ensure the generated pack output is not missing
    the `cwlVersion` in case of single tool workflow and single step workflow"""

    # Testing single tool workflow
    document_loader, workflowobj, uri = fetch_document(get_data(cwl_path))
    document_loader, _, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri)
    # generate pack output dict
    packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

    assert packed["cwlVersion"] == 'v1.0'

def test_pack_idempotence_tool():
    """Test to ensure that pack produces exactly the same document for
       an already packed document"""

    # Testing single tool
    _pack_idempotently("tests/wf/hello_single_tool.cwl")

def test_pack_idempotence_workflow():
    """Test to ensure that pack produces exactly the same document for
       an already packed document"""

    # Testing workflow
    _pack_idempotently("tests/wf/count-lines1-wf.cwl")

def _pack_idempotently(document):
    document_loader, workflowobj, uri = fetch_document(
        get_data(document))
    document_loader, _, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri)
    # generate pack output dict
    packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

    document_loader, workflowobj, uri2 = fetch_document(packed)
    document_loader, _, processobj, metadata, uri2 = validate_document(
        document_loader, workflowobj, uri)
    double_packed = json.loads(print_pack(document_loader, processobj, uri2, metadata))
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
def test_packed_workflow_execution(wf_path, job_path, namespaced):
    load_tool.loaders = {}

    document_loader, workflowobj, uri = fetch_document(
        get_data(wf_path), resolver=tool_resolver)

    document_loader, _, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri)

    packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

    assert not namespaced or "$namespaces" in packed

    wf_packed_handle, wf_packed_path = tempfile.mkstemp()
    with open(wf_packed_path, 'w') as temp_file:
        json.dump(packed, temp_file)

    normal_output = StringIO()
    packed_output = StringIO()

    normal_params = [get_data(wf_path), get_data(job_path)]
    packed_params = ['--debug', get_data(wf_packed_path), get_data(job_path)]

    assert main(normal_params, stdout=normal_output) == 0
    assert main(packed_params, stdout=packed_output) == 0

    assert json.loads(packed_output.getvalue()) == json.loads(normal_output.getvalue())

    os.close(wf_packed_handle)
    os.remove(wf_packed_path)
