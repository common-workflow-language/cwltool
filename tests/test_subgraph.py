import json
from pathlib import Path
from typing import Any

from schema_salad.utils import convert_to_dict

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.subgraph import get_step, get_subgraph
from cwltool.workflow import Workflow, default_make_tool

from .util import get_data, get_main_output


def clean(val: Any, path: str) -> Any:
    """Remove the path prefix from an string values."""
    if isinstance(val, str):
        if val.startswith(path):
            return val[len(path) + 1 :]
    if isinstance(val, dict):
        return {k: clean(v, path) for k, v in val.items()}
    if isinstance(val, list):
        return [clean(v, path) for v in val]
    return val


def test_get_subgraph() -> None:
    """Compare known correct subgraphs to generated subgraphs."""
    loading_context = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loading_context.do_update = False
    tool = load_tool(wf, loading_context)

    sg = Path(get_data("tests/subgraph")).as_uri()

    for a in (
        "file1",
        "file2",
        "file3",
        "count_output",
        "output3",
        "output4",
        "output5",
        "step1",
        "step2",
        "step3",
        "step4",
        "step5",
    ):
        assert isinstance(tool, Workflow)
        extracted = get_subgraph([wf + "#" + a], tool, loading_context)
        with open(get_data("tests/subgraph/extract_" + a + ".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted), sg)


def test_get_subgraph_long_out_form() -> None:
    """Compare subgraphs generatation when 'out' is in the long form."""
    loading_context = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/1432.cwl")).as_uri()
    loading_context.do_update = False
    tool = load_tool(wf, loading_context)

    sg = Path(get_data("tests/")).as_uri()

    assert isinstance(tool, Workflow)
    extracted = get_subgraph([wf + "#step2"], tool, loading_context)
    with open(get_data("tests/subgraph/extract_step2_1432.json")) as f:
        assert json.load(f) == clean(convert_to_dict(extracted), sg)


def test_get_step() -> None:
    loading_context = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loading_context.do_update = False
    tool = load_tool(wf, loading_context)
    assert isinstance(tool, Workflow)

    sg = Path(get_data("tests/subgraph")).as_uri()

    for a in (
        "step1",
        "step2",
        "step3",
        "step4",
        "step5",
    ):
        extracted = get_step(tool, wf + "#" + a, loading_context)
        with open(get_data("tests/subgraph/single_" + a + ".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted), sg)


def test_single_process_inherit_reqshints() -> None:
    """Inherit reqs and hints from parent(s) with --single-process."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "step1",
            get_data("tests/subgraph/env-wf2.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$cdc1e84968261d6a7575b5305945471f8be199b6"
    )


def test_single_process_inherit_hints_collision() -> None:
    """Inherit reqs and hints --single-process hints collision."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "step1",
            get_data("tests/subgraph/env-wf2_hint_collision.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$b3ec4ed1749c207e52b3a6d08c59f31d83bff519"
    )


def test_single_process_inherit_reqs_collision() -> None:
    """Inherit reqs and hints --single-process reqs collision."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "step1",
            get_data("tests/subgraph/env-wf2_req_collision.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$b3ec4ed1749c207e52b3a6d08c59f31d83bff519"
    )


def test_single_process_inherit_reqs_hints_collision() -> None:
    """Inherit reqs and hints --single-process reqs + hints collision."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "step1",
            get_data("tests/subgraph/env-wf2_hint_req_collision.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$b3ec4ed1749c207e52b3a6d08c59f31d83bff519"
    )


def test_single_process_inherit_only_hints() -> None:
    """Inherit reqs and hints --single-process only hints."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "step1",
            get_data("tests/subgraph/env-wf2_only_hint.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$ab5f2a9add5f54622dde555ac8ae9a3000e5ee0a"
    )


def test_single_process_subwf_step() -> None:
    """Inherit reqs and hints --single-process on sub-workflow step."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "sub_wf/step1",
            get_data("tests/subgraph/env-wf2_subwf.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$cdc1e84968261d6a7575b5305945471f8be199b6"
    )


def test_single_process_packed_subwf_step() -> None:
    """Inherit reqs and hints --single-process on packed sub-workflow step."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-process",
            "sub_wf/step1",
            get_data("tests/subgraph/env-wf2_subwf-packed.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$cdc1e84968261d6a7575b5305945471f8be199b6"
    )


def test_single_step_subwf_step() -> None:
    """Inherit reqs and hints --single-step on sub-workflow step."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-step",
            "sub_wf/step1",
            get_data("tests/subgraph/env-wf2_subwf.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$7608e5669ba454c61fab01c9b133b52a9a7de68c"
    )


def test_single_step_packed_subwf_step() -> None:
    """Inherit reqs and hints --single-step on packed sub-workflow step."""
    err_code, stdout, stderr = get_main_output(
        [
            "--single-step",
            "sub_wf/step1",
            get_data("tests/subgraph/env-wf2_subwf-packed.cwl"),
            get_data("tests/subgraph/env-job.json"),
        ]
    )
    assert err_code == 0
    assert (
        json.loads(stdout)["out"]["checksum"]
        == "sha1$7608e5669ba454c61fab01c9b133b52a9a7de68c"
    )


def test_print_targets_embedded_step() -> None:
    """Confirm that --print-targets works when a Workflow has embedded Processes."""
    err_code, stdout, stderr = get_main_output(
        [
            "--print-targets",
            get_data("tests/subgraph/timelimit2-wf.cwl"),
        ]
    )
    assert err_code == 0


def test_print_targets_embedded_reqsinherit() -> None:
    """Confirm --print-targets works with a step that needs a req from parent Workflow."""
    err_code, stdout, stderr = get_main_output(
        [
            "--print-targets",
            get_data("tests/wf/double-nested.cwl"),
        ]
    )
    assert err_code == 0
