import os
from distutils import spawn

import pytest

from cwltool.utils import onWindows

from .util import get_data, get_main_output, needs_docker

try:
    from galaxy.tools import deps  # type: ignore
except ImportError:
    deps = None


@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_biocontainers() -> None:
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, _ = get_main_output(["--beta-use-biocontainers", wflow, job])

    assert error_code == 0


@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda() -> None:
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-conda-dependencies", "--debug", wflow, job]
    )

    assert error_code == 0, stderr


@pytest.mark.skipif(
    not spawn.find_executable("modulecmd"), reason="modulecmd not installed"
)
def test_modules() -> None:
    wflow = get_data("tests/random_lines.cwl")
    job = get_data("tests/random_lines_job.json")
    os.environ["MODULEPATH"] = os.path.join(
        os.getcwd(), "tests/test_deps_env/modulefiles"
    )
    error_code, _, stderr = get_main_output(
        [
            "--beta-dependency-resolvers-configuration",
            "tests/test_deps_env_modules_resolvers_conf.yml",
            "--debug",
            wflow,
            job,
        ]
    )

    assert error_code == 0, stderr
