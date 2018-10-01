from cwltool.main import main

from .util import get_data


def test_missing_cwl_version():
    """no cwlVersion in the workflow"""
    assert main([get_data('tests/wf/missing_cwlVersion.cwl')]) == 1

def test_incorrect_cwl_version():
    """using cwlVersion: v0.1 in the workflow"""
    assert main([get_data('tests/wf/wrong_cwlVersion.cwl')]) == 1
