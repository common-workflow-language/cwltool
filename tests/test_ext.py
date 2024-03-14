import os
import re
from io import StringIO
from pathlib import Path

import pytest

import cwltool.process
from cwltool.main import main

from .util import get_data, get_main_output, needs_docker


@needs_docker
def test_missing_enable_ext() -> None:
    """Require that --enable-ext is provided."""
    error_code, _, _ = get_main_output(
        [get_data("tests/wf/listing_deep.cwl"), get_data("tests/listing-job.yml")]
    )
    assert error_code != 0


@needs_docker
def test_listing_deep() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/listing_deep.cwl"),
        get_data("tests/listing-job.yml"),
    ]
    assert main(params) == 0


@needs_docker
def test_cwltool_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check setting options via environment variable."""
    monkeypatch.setenv("CWLTOOL_OPTIONS", "--enable-ext")
    params = [
        get_data("tests/wf/listing_deep.cwl"),
        get_data("tests/listing-job.yml"),
    ]
    assert main(params) == 0


@needs_docker
def test_listing_shallow() -> None:
    # This fails on purpose, because it tries to access listing in a subdirectory
    # the same way that listing_deep does, but it shouldn't be expanded.
    params = [
        "--enable-ext",
        get_data("tests/wf/listing_shallow.cwl"),
        get_data("tests/listing-job.yml"),
    ]
    assert main(params) != 0


@needs_docker
def test_listing_none() -> None:
    # This fails on purpose, because it tries to access listing but it shouldn't be there.
    params = [
        "--enable-ext",
        get_data("tests/wf/listing_none.cwl"),
        get_data("tests/listing-job.yml"),
    ]
    assert main(params) != 0


@needs_docker
def test_listing_v1_0() -> None:
    # Default behavior in 1.0 is deep expansion.
    assert main([get_data("tests/wf/listing_v1_0.cwl"), get_data("tests/listing-job.yml")]) == 0


@needs_docker
def test_double_overwrite(tmp_path: Path) -> None:
    """Test that overwriting an input using cwltool:InplaceUpdateRequirement works."""
    tmp_name = str(tmp_path / "value")

    before_value, expected_value = "1", "3"

    with open(tmp_name, "w") as f:
        f.write(before_value)

    assert (
        main(
            [
                "--enable-ext",
                "--outdir",
                str(tmp_path / "outdir"),
                get_data("tests/wf/mut2.cwl"),
                "-a",
                tmp_name,
            ]
        )
        == 0
    )

    with open(tmp_name) as f:
        actual_value = f.read()

    assert actual_value == expected_value


@needs_docker
def test_disable_file_overwrite_without_ext(tmp_path: Path) -> None:
    """Test that overwriting an input using an unprefixed InplaceUpdateRequirement works."""
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()
    tmp_name = tmpdir / "value"
    outdir = tmp_path / "out"
    outdir.mkdir()
    out_name = outdir / "value"
    before_value, expected_value = "1", "2"

    with open(tmp_name, "w") as f:
        f.write(before_value)

    assert (
        main(
            [
                "--outdir",
                str(outdir),
                get_data("tests/wf/updateval.cwl"),
                "-r",
                str(tmp_name),
            ]
        )
        == 0
    )

    with open(tmp_name) as f:
        tmp_value = f.read()
    with open(out_name) as f:
        out_value = f.read()

    assert tmp_value == before_value
    assert out_value == expected_value


@needs_docker
def test_disable_dir_overwrite_without_ext(tmp_path: Path) -> None:
    """Test that we can write into a "writable" input Directory w/o ext."""
    tmp = tmp_path / "tmp"
    out = tmp_path / "outdir"
    tmp.mkdir()
    out.mkdir()
    assert main(["--outdir", str(out), get_data("tests/wf/updatedir.cwl"), "-r", str(tmp)]) == 0

    assert not os.listdir(tmp)
    assert os.listdir(out)


@needs_docker
def test_disable_file_creation_in_outdir_with_ext(tmp_path: Path) -> None:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    out = tmp_path / "outdir"
    tmp_name = tmp / "value"
    out_name = out / "value"

    before_value, expected_value = "1", "2"

    with open(tmp_name, "w") as f:
        f.write(before_value)

    params = [
        "--enable-ext",
        "--leave-outputs",
        "--outdir",
        str(out),
        get_data("tests/wf/updateval_inplace.cwl"),
        "-r",
        str(tmp_name),
    ]
    assert main(params) == 0

    with open(tmp_name) as f:
        tmp_value = f.read()

    assert tmp_value == expected_value
    assert not out_name.exists()


@needs_docker
def test_disable_dir_creation_in_outdir_with_ext(tmp_path: Path) -> None:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    out = tmp_path / "outdir"
    out.mkdir()
    params = [
        "--enable-ext",
        "--leave-outputs",
        "--outdir",
        str(out),
        get_data("tests/wf/updatedir_inplace.cwl"),
        "-r",
        str(tmp),
    ]
    assert main(params) == 0

    assert os.listdir(tmp)
    assert not os.listdir(out)


@needs_docker
def test_write_write_conflict(tmp_path: Path) -> None:
    tmp_name = tmp_path / "value"

    before_value, expected_value = "1", "2"

    with open(tmp_name, "w") as f:
        f.write(before_value)

    assert main(["--enable-ext", get_data("tests/wf/mut.cwl"), "-a", str(tmp_name)]) != 0

    with open(tmp_name) as f:
        tmp_value = f.read()

    assert tmp_value == expected_value


@pytest.mark.skip(reason="This test is non-deterministic")
def test_read_write_conflict(tmp_path: Path) -> None:
    tmp_name = tmp_path / "value"

    with open(tmp_name, "w") as f:
        f.write("1")

    assert main(["--enable-ext", get_data("tests/wf/mut3.cwl"), "-a", str(tmp_name)]) != 0


@needs_docker
def test_require_prefix_networkaccess() -> None:
    assert main(["--enable-ext", get_data("tests/wf/networkaccess.cwl")]) == 0
    assert main([get_data("tests/wf/networkaccess.cwl")]) != 0
    assert main(["--enable-ext", get_data("tests/wf/networkaccess-fail.cwl")]) != 0


@needs_docker
def test_require_prefix_workreuse(tmp_path: Path) -> None:
    assert (
        main(
            [
                "--enable-ext",
                "--outdir",
                str(tmp_path),
                get_data("tests/wf/workreuse.cwl"),
            ]
        )
        == 0
    )
    assert main([get_data("tests/wf/workreuse.cwl")]) != 0
    assert main(["--enable-ext", get_data("tests/wf/workreuse-fail.cwl")]) != 0


def test_require_prefix_timelimit() -> None:
    assert main(["--enable-ext", get_data("tests/wf/timelimit.cwl")]) == 0
    assert main([get_data("tests/wf/timelimit.cwl")]) != 0
    assert main(["--enable-ext", get_data("tests/wf/timelimit-fail.cwl")]) != 0


def test_warn_large_inputs() -> None:
    was = cwltool.process.FILE_COUNT_WARNING
    try:
        stream = StringIO()

        cwltool.process.FILE_COUNT_WARNING = 3
        main(
            [get_data("tests/wf/listing_v1_0.cwl"), get_data("tests/listing2-job.yml")],
            stderr=stream,
        )

        assert "Recursive directory listing has resulted in a large number of File" in re.sub(
            "\n  *", " ", stream.getvalue()
        )
    finally:
        cwltool.process.FILE_COUNT_WARNING = was


def test_ext_validation_no_namespace_warning() -> None:
    error_code, stdout, stderr = get_main_output(
        ["--validate", "--enable-ext", get_data("tests/wf/mpi_env.cwl")]
    )
    assert error_code == 0
    assert (
        "URI prefix 'cwltool' of 'cwltool:loop' not recognized, are you "
        "missing a $namespaces section?"
    ) not in stderr
