import pytest

from cwltool.utils import onWindows

from .util import get_data, get_main_output, needs_docker, temp_dir


try:
    from galaxy.tools import deps
except ImportError:
    deps = None

@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_biocontainers():
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    with temp_dir() as depends_dir:
        error_code, _, _ = get_main_output(
            ["--beta-use-biocontainers", "--beta-dependencies-directory",
             depends_dir, wflow, job])

    assert error_code == 0

@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda():
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    with temp_dir() as depends_dir:
        error_code, _, stderr = get_main_output(
            ["--beta-conda-dependencies", "--beta-dependencies-directory",
             depends_dir, "--debug", wflow, job])

    assert error_code == 0, stderr

@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda_wrong_name():
    wflow = get_data("tests/seqtk_seq_wrong_name.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    with temp_dir() as depends_dir:
        error_code, _, stderr = get_main_output(
            ["--beta-conda-dependencies", "--beta-dependencies-directory",
             depends_dir, "--debug", wflow, job])

    assert error_code == 0, stderr

@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_custom_config():
    config = get_data("tests/test_deps_env_resolvers_conf_rewrite.yml")
    wflow = get_data("tests/random_lines_mapping.cwl")
    job = get_data("tests/random_lines_job.json")
    with temp_dir() as depends_dir:
        error_code, _, stderr = get_main_output(
            ["--beta-dependency-resolvers-configuration", config,
                "--beta-dependencies-directory", depends_dir, "--debug", wflow,
             job])

    assert error_code == 0, stderr


