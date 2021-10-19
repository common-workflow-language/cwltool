import json
from pathlib import Path
from typing import Any

from schema_salad.utils import convert_to_dict

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.subgraph import get_step, get_subgraph
from cwltool.workflow import Workflow, default_make_tool

from .util import get_data


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
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loadingContext.do_update = False
    tool = load_tool(wf, loadingContext)

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
        extracted = get_subgraph([wf + "#" + a], tool)
        with open(get_data("tests/subgraph/extract_" + a + ".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted), sg)


def test_get_subgraph_long_out_form() -> None:
    """Compare subgraphs generatation when 'out' is in the long form."""
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/1432.cwl")).as_uri()
    loadingContext.do_update = False
    tool = load_tool(wf, loadingContext)

    sg = Path(get_data("tests/")).as_uri()

    assert isinstance(tool, Workflow)
    extracted = get_subgraph([wf + "#step2"], tool)
    with open(get_data("tests/subgraph/extract_step2_1432.json")) as f:
        assert json.load(f) == clean(convert_to_dict(extracted), sg)


def test_get_step() -> None:
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loadingContext.do_update = False
    tool = load_tool(wf, loadingContext)
    assert isinstance(tool, Workflow)

    sg = Path(get_data("tests/subgraph")).as_uri()

    for a in (
        "step1",
        "step2",
        "step3",
        "step4",
        "step5",
    ):
        extracted = get_step(tool, wf + "#" + a)
        with open(get_data("tests/subgraph/single_" + a + ".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted), sg)
