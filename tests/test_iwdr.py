import os.path
import tempfile
import os

import pytest

from cwltool.main import main
from cwltool import load_tool
from .util import (get_data, get_windows_safe_factory, windows_needs_docker,
                   needs_docker, temp_dir, needs_singularity, onWindows)

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
    saved_tempdir = tempfile.tempdir
    with temp_dir() as misc:
        tempfile.tempdir = os.path.realpath(misc)
        with temp_dir() as fifth:
            with temp_dir() as sixth:
                with temp_dir() as seventh:
                    with temp_dir() as eighth:
                        with temp_dir() as firstdir:
                            first_name = os.path.join(firstdir, "first")
                            with open(first_name, 'w+t') as first:
                                first.write("1")
                            with temp_dir() as seconddir:
                                second_name = os.path.join(seconddir, "second")
                                with open(second_name, 'w+t') as second:
                                    second.write("2")
                                with  temp_dir() as thirddir:
                                    third_name = os.path.join(thirddir, "third")
                                    with open(third_name, 'w+t') as third:
                                        third.write("3")
                                    with temp_dir() as fourthdir:
                                        fourth_name = os.path.join(fourthdir,
                                                                   "fourth")
                                        with open(fourth_name, 'w+t') as fourth:
                                            fourth.write("4")
                                        with temp_dir() as outdir:
                                            assert(main(
                                                ['--outdir', outdir,
                                                 get_data("tests/wf/iwdr_permutations.cwl"),
                                                 '--first', first_name,
                                                 '--second', second_name,
                                                 '--third', third_name,
                                                 '--fourth', fourth_name,
                                                 '--fifth', fifth,
                                                 '--sixth', sixth,
                                                 '--seventh', seventh,
                                                 '--eighth', eighth]) == 0)

@needs_docker
@pytest.mark.skipif(onWindows(), reason="Literal writable directories are "
                    "currently broken on MS Windows")
def test_iwdr_permutations_inplace():
    load_tool.loaders = {}
    saved_tempdir = tempfile.tempdir
    with temp_dir() as misc:
        tempfile.tempdir = os.path.realpath(misc)
        with temp_dir() as fifth:
            with temp_dir() as sixth:
                with temp_dir() as seventh:
                    with temp_dir() as eighth:
                        with temp_dir() as firstdir:
                            first_name = os.path.join(firstdir, "first")
                            with open(first_name, 'w+t') as first:
                                first.write("1")
                            with temp_dir() as seconddir:
                                second_name = os.path.join(seconddir, "second")
                                with open(second_name, 'w+t') as second:
                                    second.write("2")
                                with  temp_dir() as thirddir:
                                    third_name = os.path.join(thirddir, "third")
                                    with open(third_name, 'w+t') as third:
                                        third.write("3")
                                    with temp_dir() as fourthdir:
                                        fourth_name = os.path.join(fourthdir,
                                                                   "fourth")
                                        with open(fourth_name, 'w+t') as fourth:
                                            fourth.write("4")
                                        with temp_dir() as outdir:
                                            assert(main(
                                                ['--outdir', outdir,
                                                 '--enable-ext',
                                                 '--overrides',
                                                 get_data("tests/wf/iwdr_permutations_inplace.yml"),
                                                 get_data("tests/wf/iwdr_permutations.cwl"),
                                                 '--first', first_name,
                                                 '--second', second_name,
                                                 '--third', third_name,
                                                 '--fourth', fourth_name,
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
