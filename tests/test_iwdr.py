import os
import tempfile

from cwltool import load_tool
from cwltool.main import main

from .util import (
    get_data,
    get_main_output,
    get_windows_safe_factory,
    needs_docker,
    needs_singularity,
    temp_dir,
    windows_needs_docker,
)


@windows_needs_docker
def test_newline_in_entry():
    """Files in a InitialWorkingDirectory are created with a newline character."""
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/wf/iwdr-entry.cwl"))
    assert echo(message="hello") == {"out": "CONFIGVAR=hello\n"}


@needs_docker
def test_empty_file_creation():
    """An empty file can be created in InitialWorkingDirectory."""
    err_code, _, _ = get_main_output([get_data("tests/wf/iwdr-empty.cwl")])
    assert err_code == 0


@needs_docker
def test_iwdr_permutations():
    saved_tempdir = tempfile.tempdir
    with temp_dir() as misc:
        tempfile.tempdir = os.path.realpath(misc)
        with temp_dir() as fifth:
            with temp_dir() as sixth:
                with temp_dir() as seventh:
                    with temp_dir() as eighth:
                        with tempfile.NamedTemporaryFile() as first:
                            with tempfile.NamedTemporaryFile() as second:
                                with tempfile.NamedTemporaryFile() as third:
                                    with tempfile.NamedTemporaryFile() as fourth:
                                        with temp_dir() as outdir:
                                            assert (
                                                main(
                                                    [
                                                        "--outdir",
                                                        outdir,
                                                        get_data(
                                                            "tests/wf/iwdr_permutations.cwl"
                                                        ),
                                                        "--first",
                                                        first.name,
                                                        "--second",
                                                        second.name,
                                                        "--third",
                                                        third.name,
                                                        "--fourth",
                                                        fourth.name,
                                                        "--fifth",
                                                        fifth,
                                                        "--sixth",
                                                        sixth,
                                                        "--seventh",
                                                        seventh,
                                                        "--eighth",
                                                        eighth,
                                                    ]
                                                )
                                                == 0
                                            )
    tempfile.tempdir = saved_tempdir


@needs_docker
def test_iwdr_permutations_inplace():
    saved_tempdir = tempfile.tempdir
    with temp_dir() as misc:
        tempfile.tempdir = os.path.realpath(misc)
        with temp_dir() as fifth:
            with temp_dir() as sixth:
                with temp_dir() as seventh:
                    with temp_dir() as eighth:
                        with tempfile.NamedTemporaryFile() as first:
                            with tempfile.NamedTemporaryFile() as second:
                                with tempfile.NamedTemporaryFile() as third:
                                    with tempfile.NamedTemporaryFile() as fourth:
                                        with temp_dir() as outdir:
                                            assert (
                                                main(
                                                    [
                                                        "--outdir",
                                                        outdir,
                                                        "--enable-ext",
                                                        "--overrides",
                                                        get_data(
                                                            "tests/wf/iwdr_permutations_inplace.yml"
                                                        ),
                                                        get_data(
                                                            "tests/wf/iwdr_permutations.cwl"
                                                        ),
                                                        "--first",
                                                        first.name,
                                                        "--second",
                                                        second.name,
                                                        "--third",
                                                        third.name,
                                                        "--fourth",
                                                        fourth.name,
                                                        "--fifth",
                                                        fifth,
                                                        "--sixth",
                                                        sixth,
                                                        "--seventh",
                                                        seventh,
                                                        "--eighth",
                                                        eighth,
                                                    ]
                                                )
                                                == 0
                                            )
    tempfile.tempdir = saved_tempdir


@needs_singularity
def test_iwdr_permutations_singularity():
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert (
                                            main(
                                                [
                                                    "--outdir",
                                                    outdir,
                                                    "--singularity",
                                                    get_data(
                                                        "tests/wf/iwdr_permutations.cwl"
                                                    ),
                                                    "--first",
                                                    first.name,
                                                    "--second",
                                                    second.name,
                                                    "--third",
                                                    third.name,
                                                    "--fourth",
                                                    fourth.name,
                                                    "--fifth",
                                                    fifth,
                                                    "--sixth",
                                                    sixth,
                                                    "--seventh",
                                                    seventh,
                                                    "--eighth",
                                                    eighth,
                                                ]
                                            )
                                            == 0
                                        )


@needs_singularity
def test_iwdr_permutations_singularity_inplace():
    with temp_dir() as fifth:
        with temp_dir() as sixth:
            with temp_dir() as seventh:
                with temp_dir() as eighth:
                    with tempfile.NamedTemporaryFile() as first:
                        with tempfile.NamedTemporaryFile() as second:
                            with tempfile.NamedTemporaryFile() as third:
                                with tempfile.NamedTemporaryFile() as fourth:
                                    with temp_dir() as outdir:
                                        assert (
                                            main(
                                                [
                                                    "--outdir",
                                                    outdir,
                                                    "--singularity",
                                                    "--enable-ext",
                                                    "--overrides",
                                                    get_data(
                                                        "tests/wf/iwdr_permutations_inplace.yml"
                                                    ),
                                                    get_data(
                                                        "tests/wf/iwdr_permutations.cwl"
                                                    ),
                                                    "--first",
                                                    first.name,
                                                    "--second",
                                                    second.name,
                                                    "--third",
                                                    third.name,
                                                    "--fourth",
                                                    fourth.name,
                                                    "--fifth",
                                                    fifth,
                                                    "--sixth",
                                                    sixth,
                                                    "--seventh",
                                                    seventh,
                                                    "--eighth",
                                                    eighth,
                                                ]
                                            )
                                            == 0
                                        )
