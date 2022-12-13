"""InitialWorkDirRequirement related tests."""
import json
import re
from pathlib import Path
from stat import S_IWGRP, S_IWOTH, S_IWRITE
from typing import Any

from cwltool.factory import Factory
from cwltool.main import main

from .util import get_data, get_main_output, needs_docker, needs_singularity


def test_newline_in_entry() -> None:
    """Files in a InitialWorkingDirectory are created with a newline character."""
    factory = Factory()
    echo = factory.make(get_data("tests/wf/iwdr-entry.cwl"))
    assert echo(message="hello") == {"out": "CONFIGVAR=hello\n"}


@needs_docker
def test_empty_file_creation() -> None:
    """An empty file can be created in InitialWorkingDirectory."""
    err_code, _, _ = get_main_output([get_data("tests/wf/iwdr-empty.cwl")])
    assert err_code == 0


def test_passthrough_successive(tmp_path: Path) -> None:
    """An empty file can be successively passed through a subdir of InitialWorkingDirectory."""
    err_code, _, _ = get_main_output(
        [
            "--outdir",
            str(tmp_path),
            get_data("tests/wf/iwdr-passthrough-successive.cwl"),
        ]
    )
    assert err_code == 0
    children = sorted(
        tmp_path.glob("*")
    )  # This input directory should be left pristine.
    assert len(children) == 1
    subdir = tmp_path / children[0]
    assert len(sorted(subdir.glob("*"))) == 1
    assert (subdir / "file").exists()


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


def test_bad_listing_expression(tmp_path: Path) -> None:
    """Confirm better error message for bad listing expression."""
    err_code, _, stderr = get_main_output(
        [
            "--out",
            str(tmp_path),
            get_data("tests/iwdr_bad_expr.cwl"),
            "--example={}".format(get_data("tests/__init__.py")),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "Expression in a 'InitialWorkdirRequirement.listing' field must return "
        "a list containing zero or more of: File or Directory objects; Dirent "
        "objects. Got '42' among the results" in stderr
    )
    assert err_code == 1


@needs_docker
def test_iwdr_permutations(tmp_path_factory: Any) -> None:
    misc = tmp_path_factory.mktemp("misc")
    fifth = misc / "fifth"
    fifth.mkdir()
    sixth = misc / "sixth"
    sixth.mkdir()
    seventh = misc / "seventh"
    seventh.mkdir()
    eighth = misc / "eighth"
    eighth.mkdir()
    first = misc / "first"
    first.touch()
    second = misc / "second"
    second.touch()
    third = misc / "third"
    third.touch()
    fourth = misc / "fourth"
    fourth.touch()
    eleventh = misc / "eleventh"
    eleventh.touch()
    twelfth = misc / "twelfth"
    twelfth.touch()
    outdir = str(tmp_path_factory.mktemp("outdir"))
    err_code, stdout, _ = get_main_output(
        [
            "--outdir",
            outdir,
            "--debug",
            get_data("tests/wf/iwdr_permutations.cwl"),
            "--first",
            str(first),
            "--second",
            str(second),
            "--third",
            str(third),
            "--fourth",
            str(fourth),
            "--fifth",
            str(fifth),
            "--sixth",
            str(sixth),
            "--seventh",
            str(seventh),
            "--eighth",
            str(eighth),
            "--eleventh",
            str(eleventh),
            "--eleventh",
            str(twelfth),
        ]
    )
    assert err_code == 0
    log = json.loads(stdout)["log"]
    with open(log["path"]) as log_h:
        log_text = log_h.read()
    assert log["checksum"] == "sha1$bc51ebb3f65ca44282789dd1e6de9747d8abe75f", log_text


def test_iwdr_permutations_readonly(tmp_path_factory: Any) -> None:
    """Confirm that readonly input files are properly made writable."""
    misc = tmp_path_factory.mktemp("misc")
    fifth = misc / "fifth"
    fifth.mkdir()
    sixth = misc / "sixth"
    sixth.mkdir()
    fifth_file = fifth / "bar"
    fifth_dir = fifth / "foo"
    fifth_file.touch()
    fifth_dir.mkdir()
    sixth = tmp_path_factory.mktemp("sixth")
    first = misc / "first"
    first.touch()
    second = misc / "second"
    second.touch()
    outdir = str(tmp_path_factory.mktemp("outdir"))
    for entry in [first, second, fifth, sixth, fifth_file, fifth_dir]:
        mode = entry.stat().st_mode
        ro_mask = 0o777 ^ (S_IWRITE | S_IWGRP | S_IWOTH)
        entry.chmod(mode & ro_mask)
    assert (
        main(
            [
                "--no-container",
                "--debug",
                "--leave-outputs",
                "--outdir",
                outdir,
                get_data("tests/wf/iwdr_permutations_nocontainer.cwl"),
                "--first",
                str(first),
                "--second",
                str(second),
                "--fifth",
                str(fifth),
                "--sixth",
                str(sixth),
            ]
        )
        == 0
    )
    for entry in [first, second, fifth, sixth, fifth_file, fifth_dir]:
        try:
            mode = entry.stat().st_mode
            entry.chmod(mode | S_IWRITE)
        except PermissionError:
            pass


@needs_docker
def test_iwdr_permutations_inplace(tmp_path_factory: Any) -> None:
    misc = tmp_path_factory.mktemp("misc")
    fifth = misc / "fifth"
    fifth.mkdir()
    sixth = misc / "sixth"
    sixth.mkdir()
    seventh = misc / "seventh"
    seventh.mkdir()
    eighth = misc / "eighth"
    eighth.mkdir()
    first = misc / "first"
    first.touch()
    second = misc / "second"
    second.touch()
    third = misc / "third"
    third.touch()
    fourth = misc / "fourth"
    fourth.touch()
    eleventh = misc / "eleventh"
    eleventh.touch()
    twelfth = misc / "twelfth"
    twelfth.touch()
    outdir = str(tmp_path_factory.mktemp("outdir"))
    err_code, stdout, _ = get_main_output(
        [
            "--outdir",
            outdir,
            "--enable-ext",
            "--overrides",
            get_data("tests/wf/iwdr_permutations_inplace.yml"),
            get_data("tests/wf/iwdr_permutations.cwl"),
            "--first",
            str(first),
            "--second",
            str(second),
            "--third",
            str(third),
            "--fourth",
            str(fourth),
            "--fifth",
            str(fifth),
            "--sixth",
            str(sixth),
            "--seventh",
            str(seventh),
            "--eighth",
            str(eighth),
            "--eleventh",
            str(eleventh),
            "--eleventh",
            str(twelfth),
        ]
    )
    assert err_code == 0
    log = json.loads(stdout)["log"]
    with open(log["path"]) as log_h:
        log_text = log_h.read()
    assert log["checksum"] == "sha1$bc51ebb3f65ca44282789dd1e6de9747d8abe75f", log_text


@needs_singularity
def test_iwdr_permutations_singularity(tmp_path_factory: Any) -> None:
    misc = tmp_path_factory.mktemp("misc")
    fifth = misc / "fifth"
    fifth.mkdir()
    sixth = misc / "sixth"
    sixth.mkdir()
    seventh = misc / "seventh"
    seventh.mkdir()
    eighth = misc / "eighth"
    eighth.mkdir()
    first = misc / "first"
    first.touch()
    second = misc / "second"
    second.touch()
    third = misc / "third"
    third.touch()
    fourth = misc / "fourth"
    fourth.touch()
    eleventh = misc / "eleventh"
    eleventh.touch()
    twelfth = misc / "twelfth"
    twelfth.touch()
    outdir = str(tmp_path_factory.mktemp("outdir"))
    err_code, stdout, _ = get_main_output(
        [
            "--outdir",
            outdir,
            "--debug",
            "--singularity",
            get_data("tests/wf/iwdr_permutations.cwl"),
            "--first",
            str(first),
            "--second",
            str(second),
            "--third",
            str(third),
            "--fourth",
            str(fourth),
            "--fifth",
            str(fifth),
            "--sixth",
            str(sixth),
            "--seventh",
            str(seventh),
            "--eighth",
            str(eighth),
            "--eleventh",
            str(eleventh),
            "--eleventh",
            str(twelfth),
        ]
    )
    assert err_code == 0
    log = json.loads(stdout)["log"]
    with open(log["path"]) as log_h:
        log_text = log_h.read()
    assert log["checksum"] == "sha1$bc51ebb3f65ca44282789dd1e6de9747d8abe75f", log_text


@needs_singularity
def test_iwdr_permutations_singularity_inplace(tmp_path_factory: Any) -> None:
    """IWDR tests using --singularity and a forced InplaceUpdateRequirement."""
    misc = tmp_path_factory.mktemp("misc")
    fifth = misc / "fifth"
    fifth.mkdir()
    sixth = misc / "sixth"
    sixth.mkdir()
    seventh = misc / "seventh"
    seventh.mkdir()
    eighth = misc / "eighth"
    eighth.mkdir()
    first = misc / "first"
    first.touch()
    second = misc / "second"
    second.touch()
    third = misc / "third"
    third.touch()
    fourth = misc / "fourth"
    fourth.touch()
    eleventh = misc / "eleventh"
    eleventh.touch()
    twelfth = misc / "twelfth"
    twelfth.touch()
    outdir = str(tmp_path_factory.mktemp("outdir"))
    assert (
        main(
            [
                "--outdir",
                outdir,
                "--singularity",
                "--enable-ext",
                "--enable-dev",
                "--overrides",
                get_data("tests/wf/iwdr_permutations_inplace.yml"),
                get_data("tests/wf/iwdr_permutations.cwl"),
                "--first",
                str(first),
                "--second",
                str(second),
                "--third",
                str(third),
                "--fourth",
                str(fourth),
                "--fifth",
                str(fifth),
                "--sixth",
                str(sixth),
                "--seventh",
                str(seventh),
                "--eighth",
                str(eighth),
                "--eleventh",
                str(eleventh),
                "--eleventh",
                str(twelfth),
            ]
        )
        == 0
    )
