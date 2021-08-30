import json
from pathlib import Path
from typing import Any

from schema_salad.utils import convert_to_dict

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.subgraph import get_step, get_subgraph
from cwltool.workflow import Workflow, default_make_tool

from .util import get_data


def test_get_subgraph() -> None:
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loadingContext.do_update = False
    tool = load_tool(wf, loadingContext)

    sg = Path(get_data("tests/subgraph")).as_uri()

    def clean(val: Any) -> Any:
        if isinstance(val, str):
            if val.startswith(sg):
                return val[len(sg) + 1 :]
        if isinstance(val, dict):
            return {k: clean(v) for k, v in val.items()}
        if isinstance(val, list):
            return [clean(v) for v in val]
        return val

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
            assert json.load(f) == clean(convert_to_dict(extracted))


def test_get_step() -> None:
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri()
    loadingContext.do_update = False
    tool = load_tool(wf, loadingContext)
    assert isinstance(tool, Workflow)

    sg = Path(get_data("tests/subgraph")).as_uri()

    def clean(val: Any) -> Any:
        if isinstance(val, str):
            if val.startswith(sg):
                return val[len(sg) + 1 :]
        if isinstance(val, dict):
            return {k: clean(v) for k, v in val.items()}
        if isinstance(val, list):
            return [clean(v) for v in val]
        return val

    for a in (
        "step1",
        "step2",
        "step3",
        "step4",
        "step5",
    ):
        extracted = get_step(tool, wf + "#" + a)
        with open(get_data("tests/subgraph/single_" + a + ".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted))
