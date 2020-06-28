import pytest  # type: ignore

from cwltool.main import main

from .util import get_data, needs_docker

bad_flows = ["tests/wf/badout1.cwl", "tests/wf/badout2.cwl", "tests/wf/badout3.cwl"]


@needs_docker  # type: ignore
@pytest.mark.parametrize("bad_flow", bad_flows)  # type: ignore
def test_output_checking(bad_flow: str) -> None:
    assert main([get_data(bad_flow)]) == 1
