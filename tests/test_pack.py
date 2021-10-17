import json
import os
import tempfile
from collections.abc import Sized
from functools import partial
from io import StringIO
from pathlib import Path
from typing import Dict

import pytest
from schema_salad.utils import yaml_no_ts

import cwltool.pack
import cwltool.workflow
from cwltool.context import LoadingContext
from cwltool.load_tool import fetch_document, resolve_and_validate_document
from cwltool.main import main, make_relative, print_pack
from cwltool.resolver import tool_resolver
from cwltool.utils import adjustDirObjs, adjustFileObjs

from .util import get_data, needs_docker


@pytest.mark.parametrize(
    "unpacked,expected",
    [
        ("tests/wf/revsort.cwl", "tests/wf/expect_packed.cwl"),
        (
            "tests/wf/operation/operation-single.cwl",
            "tests/wf/operation/expect_operation-single_packed.cwl",
        ),
        ("tests/wf/trick_revsort.cwl", "tests/wf/expect_trick_packed.cwl"),
        (
            "tests/wf/iwd-passthrough1.cwl",
            "tests/wf/expect_iwd-passthrough1_packed.cwl",
        ),
        (
            "tests/wf/revsort_datetime.cwl",
            "tests/wf/expect_revsort_datetime_packed.cwl",
        ),
    ],
)
def test_packing(unpacked: str, expected: str) -> None:
    """Compare expected version reality with various workflows and --pack."""
    loadingContext, workflowobj, uri = fetch_document(get_data(unpacked))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )

    packed = json.loads(print_pack(loadingContext, uri))
    context_dir = os.path.abspath(os.path.dirname(get_data(unpacked)))
    adjustFileObjs(packed, partial(make_relative, context_dir))
    adjustDirObjs(packed, partial(make_relative, context_dir))

    with open(get_data(expected)) as packed_file:
        expect_packed = json.load(packed_file)

    if "$schemas" in expect_packed:
        assert "$schemas" in packed
        packed_schemas = packed["$schemas"]
        assert isinstance(packed_schemas, Sized)
        assert len(packed_schemas) == len(expect_packed["$schemas"])
        del packed["$schemas"]
        del expect_packed["$schemas"]

    assert packed == expect_packed


def test_pack_single_tool() -> None:
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/formattest.cwl")
    )
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    loader.resolve_ref(uri)[0]

    packed = cwltool.pack.pack(loadingContext, uri)
    assert "$schemas" in packed


def test_pack_fragment() -> None:
    yaml = yaml_no_ts()

    with open(get_data("tests/wf/scatter2_subwf.cwl")) as packed_file:
        expect_packed = yaml.load(packed_file)

    loadingContext, workflowobj, uri = fetch_document(get_data("tests/wf/scatter2.cwl"))
    packed = cwltool.pack.pack(loadingContext, uri + "#scatterstep/mysub")
    adjustFileObjs(
        packed, partial(make_relative, os.path.abspath(get_data("tests/wf")))
    )
    adjustDirObjs(packed, partial(make_relative, os.path.abspath(get_data("tests/wf"))))

    packed_result = json.dumps(packed, sort_keys=True, indent=2)
    expected = json.dumps(expect_packed, sort_keys=True, indent=2)

    assert packed_result == expected


def test_pack_rewrites() -> None:
    rewrites = {}  # type: Dict[str, str]

    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/default-wf5.cwl")
    )
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    loader.resolve_ref(uri)[0]

    cwltool.pack.pack(
        loadingContext,
        uri,
        rewrite_out=rewrites,
    )

    assert len(rewrites) == 6


cwl_missing_version_paths = [
    "tests/wf/hello_single_tool.cwl",
    "tests/wf/hello-workflow.cwl",
]


@pytest.mark.parametrize("cwl_path", cwl_missing_version_paths)
def test_pack_missing_cwlVersion(cwl_path: str) -> None:
    """Ensure the generated pack output is not missing the `cwlVersion` in case of single tool workflow and single step workflow."""
    # Testing single tool workflow
    loadingContext, workflowobj, uri = fetch_document(get_data(cwl_path))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed = json.loads(print_pack(loadingContext, uri))

    assert packed["cwlVersion"] == "v1.0"


def test_pack_idempotence_tool(tmp_path: Path) -> None:
    """Ensure that pack produces exactly the same document for an already packed CommandLineTool."""
    _pack_idempotently("tests/wf/hello_single_tool.cwl", tmp_path)


def test_pack_idempotence_workflow(tmp_path: Path) -> None:
    """Ensure that pack produces exactly the same document for an already packed workflow."""
    _pack_idempotently("tests/wf/count-lines1-wf.cwl", tmp_path)


def _pack_idempotently(document: str, tmp_path: Path) -> None:
    loadingContext, workflowobj, uri = fetch_document(get_data(document))
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    loader.resolve_ref(uri)[0]

    # generate pack output dict
    packed_text = print_pack(loadingContext, uri)
    packed = json.loads(packed_text)

    tmp_name = tmp_path / "packed.cwl"
    tmp = tmp_name.open(mode="w")
    tmp.write(packed_text)
    tmp.flush()
    tmp.close()

    loadingContext, workflowobj, uri2 = fetch_document(tmp.name)
    loadingContext.do_update = False
    loadingContext, uri2 = resolve_and_validate_document(
        loadingContext, workflowobj, uri2
    )
    loader2 = loadingContext.loader
    assert loader2
    loader2.resolve_ref(uri2)[0]

    # generate pack output dict
    packed_text = print_pack(loadingContext, uri2)
    double_packed = json.loads(packed_text)

    assert uri != uri2
    assert packed == double_packed


cwl_to_run = [
    ("tests/wf/count-lines1-wf.cwl", "tests/wf/wc-job.json", False),
    ("tests/wf/formattest.cwl", "tests/wf/formattest-job.json", True),
]


@needs_docker
@pytest.mark.parametrize("wf_path,job_path,namespaced", cwl_to_run)
def test_packed_workflow_execution(
    wf_path: str, job_path: str, namespaced: bool, tmp_path: Path
) -> None:
    loadingContext = LoadingContext()
    loadingContext.resolver = tool_resolver
    loadingContext, workflowobj, uri = fetch_document(get_data(wf_path), loadingContext)
    loadingContext.do_update = False
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    loader.resolve_ref(uri)[0]
    packed = json.loads(print_pack(loadingContext, uri))

    assert not namespaced or "$namespaces" in packed

    wf_packed_handle, wf_packed_path = tempfile.mkstemp()
    with open(wf_packed_path, "w") as temp_file:
        json.dump(packed, temp_file)

    normal_output = StringIO()
    packed_output = StringIO()

    normal_params = ["--outdir", str(tmp_path), get_data(wf_path), get_data(job_path)]
    packed_params = [
        "--outdir",
        str(tmp_path),
        "--debug",
        wf_packed_path,
        get_data(job_path),
    ]

    assert main(normal_params, stdout=normal_output) == 0
    assert main(packed_params, stdout=packed_output) == 0

    assert json.loads(packed_output.getvalue()) == json.loads(normal_output.getvalue())

    os.close(wf_packed_handle)
    os.remove(wf_packed_path)
