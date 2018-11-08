import os

from six.moves import urllib

import pytest
import json

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.workflow import default_make_tool
from cwltool.subgraph import get_subgraph
from schema_salad.utils import convert_to_dict
from cwltool.resolver import Path, resolve_local
from .util import get_data, working_directory
from six import string_types
from .test_fetch import norm

def test_get_subgraph():
    loadingContext = LoadingContext({"construct_tool_object": default_make_tool})
    wf = norm(Path(get_data("tests/subgraph/count-lines1-wf.cwl")).as_uri())
    tool = load_tool(wf, loadingContext)

    sg = norm(Path(get_data("tests/subgraph")).as_uri())

    def clean(val):
        if isinstance(val, string_types):
            if val.startswith(sg):
                return val[len(sg)+1:]
        if isinstance(val, dict):
            return {k: clean(v) for k,v in val.items()}
        if isinstance(val, list):
            return [clean(v) for v in val]
        return val

    for a in ("file1", "file2", "file3", "count_output",
              "output3", "output4", "output5",
              "step1", "step2", "step3", "step4", "step5"):
        extracted = get_subgraph([wf+"#"+a], tool)
        with open(get_data("tests/subgraph/extract_"+a+".json")) as f:
            assert json.load(f) == clean(convert_to_dict(extracted))
