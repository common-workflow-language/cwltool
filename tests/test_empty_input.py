try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

from cwltool.main import main
from .util import get_data, temp_dir, windows_needs_docker

@windows_needs_docker
def test_empty_input():
    empty_json = '{}'
    empty_input = StringIO(empty_json)

    with temp_dir() as tmpdir:
        params = ['--outdir', tmpdir, get_data('tests/wf/no-parameters-echo.cwl'), '-']

        try:
            assert main(params, stdin=empty_input) == 0
        except SystemExit as err:
            assert err.code == 0
