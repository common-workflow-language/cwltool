from typing_extensions import Text

import pytest

from cwltool.utils import onWindows
from .util import get_data, get_main_output, needs_docker, temp_dir


try:
    from galaxy.tools import deps
except ImportError:
    deps = None


@pytest.fixture(scope="module")
def depends_dir(tmpdir_factory):
    ddir = tmpdir_factory.mktemp("cwltool_deps")
    yield Text(ddir)
    ddir.remove()

@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_biocontainers(depends_dir):
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, _ = get_main_output(
        ["--beta-use-biocontainers", "--beta-dependencies-directory",
         depends_dir, wflow, job])

    assert error_code == 0

@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda(depends_dir):
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-conda-dependencies", "--beta-dependencies-directory",
         depends_dir, "--debug", wflow, job])

    assert error_code == 0, stderr

@pytest.mark.skipif(onWindows(), reason="bioconda currently not working on MS Windows")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda_wrong_name(depends_dir):
    wflow = get_data("tests/seqtk_seq_wrong_name.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-conda-dependencies", "--beta-dependencies-directory",
         depends_dir, "--debug", wflow, job])

    assert error_code == 0, stderr

@pytest.mark.skipif(onWindows(), reason="custom dependency resolver is Unix only for now.")
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_custom_config(depends_dir, tmpdir):
    config = tmpdir.join("test_deps_env_resolvers_conf_rewrite.yml")
    with config.open(mode="w") as handle:
        handle.write("- type: galaxy_packages\n  base_path: {}\n"
        "  mapping_files: {}".format(get_data("tests/test_deps_env"),
                                     get_data("tests/test_deps_mapping.yml")))
    wflow = get_data("tests/random_lines_mapping.cwl")
    job = get_data("tests/random_lines_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-dependency-resolvers-configuration", Text(config),
         "--beta-dependencies-directory", depends_dir, "--debug", wflow,
         job])

    assert error_code == 0, stderr
    tmpdir.remove()
