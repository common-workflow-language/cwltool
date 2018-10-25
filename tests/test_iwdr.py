import tempfile
from cwltool.main import main
from cwltool import load_tool
from .util import (get_data, get_windows_safe_factory, windows_needs_docker,
                   needs_docker, temp_dir, needs_singularity)

@windows_needs_docker
def test_newline_in_entry():
    """
    test that files in InitialWorkingDirectory are created with a newline character
    """
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/wf/iwdr-entry.cwl"))
    assert echo(message="hello") == {"out": "CONFIGVAR=hello\n"}

@needs_docker
def test_iwdr_permutations():
    load_tool.loaders = {}
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert(main(
                                            ['--outdir', outdir,
                                             get_data("tests/wf/iwdr_permutations.cwl"),
                                             '--first', first.name,
                                             '--second', second.name,
                                             '--third', third.name,
                                             '--fourth', fourth.name,
                                             '--fifth', fifth,
                                             '--sixth', sixth,
                                             '--seventh', seventh,
                                             '--eighth', eighth]) == 0)

@needs_docker
def test_iwdr_permutations_inplace():
    load_tool.loaders = {}
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert(main(
                                            ['--outdir', outdir,
                                             '--enable-ext',
                                             '--overrides',
                                             get_data("tests/wf/iwdr_permutations_inplace.yml"),
                                             get_data("tests/wf/iwdr_permutations.cwl"),
                                             '--first', first.name,
                                             '--second', second.name,
                                             '--third', third.name,
                                             '--fourth', fourth.name,
                                             '--fifth', fifth,
                                             '--sixth', sixth,
                                             '--seventh', seventh,
                                             '--eighth', eighth]) == 0)

@needs_singularity
def test_iwdr_permutations_singularity():
    load_tool.loaders = {}
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert(main(
                                            ['--outdir', outdir,
                                             '--singularity',
                                             get_data("tests/wf/iwdr_permutations.cwl"),
                                             '--first', first.name,
                                             '--second', second.name,
                                             '--third', third.name,
                                             '--fourth', fourth.name,
                                             '--fifth', fifth,
                                             '--sixth', sixth,
                                             '--seventh', seventh,
                                             '--eighth', eighth]) == 0)

@needs_singularity
def test_iwdr_permutations_singularity_inplace():
    load_tool.loaders = {}
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert(main(
                                            ['--outdir', outdir,
                                             '--singularity',
                                             '--enable-ext',
                                             '--overrides',
                                             get_data("tests/wf/iwdr_permutations_inplace.yml"),
                                             get_data("tests/wf/iwdr_permutations.cwl"),
                                             '--first', first.name,
                                             '--second', second.name,
                                             '--third', third.name,
                                             '--fourth', fourth.name,
                                             '--fifth', fifth,
                                             '--sixth', sixth,
                                             '--seventh', seventh,
                                             '--eighth', eighth]) == 0)
