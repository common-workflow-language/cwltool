import pytest

import pytest

from cwltool.utils import onWindows

from .util import get_data, get_main_output, needs_docker


try:
    from galaxy.tools import deps
except ImportError:
    deps = None

@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_biocontainers():
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, _ = get_main_output(
        ["--beta-use-biocontainers", wflow, job])

    assert error_code == 0

@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda():
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-conda-dependencies", "--debug", wflow, job])

    assert error_code == 0, stderr
