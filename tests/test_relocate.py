from cwltool.main import main

from .util import get_data, needs_docker

@needs_docker
def test_for_910():
    assert main([get_data('tests/wf/910.cwl')]) == 0
    assert main([get_data('tests/wf/910.cwl')]) == 0
