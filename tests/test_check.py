import pytest

from cwltool.main import main

from .util import get_data, needs_docker


bad_flows = [
    'tests/wf/badout1.cwl',
    'tests/wf/badout2.cwl',
    'tests/wf/badout3.cwl'
]

@needs_docker
@pytest.mark.parametrize('bad_flow', bad_flows)
def test_output_checking(bad_flow):
    assert main([get_data(bad_flow)]) == 1
