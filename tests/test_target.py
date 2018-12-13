from cwltool.main import main
from cwltool import load_tool

from .util import get_data, windows_needs_docker


@windows_needs_docker
def test_target():
    load_tool.loaders = {}
    """Test --target option successful."""
    test_file = "tests/wf/scatter-wf4.cwl"
    exit_code = main(['--target', 'out', get_data(test_file),
                     '--inp1', 'INP1', '--inp2', 'INP2'])
    assert exit_code == 0


def test_wrong_target():
    load_tool.loaders = {}
    """Test --target option when value is wrong."""
    test_file = "tests/wf/scatter-wf4.cwl"
    exit_code = main(['--target', 'dummy_target',
                     get_data(test_file),
                     '--inp1', 'INP1', '--inp2', 'INP2'])
    assert exit_code == 1


@windows_needs_docker    
def test_target_packed():
    load_tool.loaders = {}
    """Test --target option with packed workflow schema."""
    test_file = "tests/wf/scatter-wf4.json"
    exit_code = main(['--target', 'out',
                     get_data(test_file),
                     '--inp1', 'INP1', '--inp2', 'INP2'])
    assert exit_code == 0
