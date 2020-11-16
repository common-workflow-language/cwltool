import os
import tempfile
from pathlib import Path

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
def test_newline_in_entry() -> None:
    """Files in a InitialWorkingDirectory are created with a newline character."""
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/wf/iwdr-entry.cwl"))
    assert echo(message="hello") == {"out": "CONFIGVAR=hello\n"}


@needs_docker
def test_empty_file_creation() -> None:
    """An empty file can be created in InitialWorkingDirectory."""
    err_code, _, _ = get_main_output([get_data("tests/wf/iwdr-empty.cwl")])
    assert err_code == 0


@needs_docker
def test_directory_literal_with_real_inputs_inside(tmp_path: Path) -> None:
    """Cope with unmoveable files in the output directory created by Docker+IWDR."""
    err_code, _, _ = get_main_output(
        [
            "--out",
            str(tmp_path),
            get_data("tests/iwdr_dir_literal_real_file.cwl"),
            "--example={}".format(get_data("tests/__init__.py")),
        ]
    )
    assert err_code == 0


@needs_docker
def test_iwdr_permutations() -> None:
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
                                                        "--enable-dev",
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
def test_iwdr_permutations_inplace() -> None:
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
                                                        "--enable-dev",
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
def test_iwdr_permutations_singularity() -> None:
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
                                                    "--enable-dev",
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
def test_iwdr_permutations_singularity_inplace() -> None:
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
                                                    "--enable-dev",
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
