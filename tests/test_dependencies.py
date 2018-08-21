from __future__ import absolute_import

from cwltool.utils import onWindows

from .util import get_data, needs_docker
from .test_examples import TestCmdLine

import pytest

try:
    from galaxy.tools.deps.requirements import ToolRequirement, ToolRequirements
    from galaxy.tools import deps
except ImportError:
    deps = None

class TestBetaDependenciesResolver(TestCmdLine):

    @needs_docker
    def test_biocontainers(self):
        if not deps:
            pytest.skip("galaxy-lib is not installed.")
        wflow = get_data("tests/seqtk_seq.cwl")
        job = get_data("tests/seqtk_seq_job.json")
        error_code, stdout, stderr = self.get_main_output(
            ["--beta-use-biocontainers", wflow, job])
        print(stderr)
        print(stdout)
        assert error_code is 0

    def test_bioconda(self):
        if onWindows() or not deps:
            pytest.skip("bioconda currently not working on MS Windows.")
        elif not deps:
            pytest.skip("galaxy-lib is not installed.")
        wflow = get_data("tests/seqtk_seq.cwl")
        job = get_data("tests/seqtk_seq_job.json")
        error_code, stdout, stderr = self.get_main_output(
            ["--beta-conda-dependencies", "--debug", wflow, job])
        print(stderr)
        print(stdout)
        assert error_code is 0
