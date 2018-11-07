from os import listdir

from cwltool.main import main
from .util import get_data, temp_dir, needs_docker, windows_needs_docker

@needs_docker
def test_same_content():

    with temp_dir() as tmpdir:
        params = ['--outdir', tmpdir, get_data('tests/wf/path-conflict-same-content.cwl')]

        assert main(params) == 0
        assert len(listdir(tmpdir)) in [1, 2],\
            'One or two files must be present since their contents are the same'

@windows_needs_docker
def test_different_content():
    with temp_dir() as tmpdir:
        params = ['--outdir', tmpdir, get_data('tests/wf/path-conflict-different-content.cwl')]

        assert main(params) == 0
        assert len(listdir(tmpdir)) == 2,\
            'Two files must be present since their contents are differents'
