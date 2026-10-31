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


def test_missing_enable_ext_suggests_flag(caplog: pytest.LogCaptureFixture) -> None:
    """Name the extension and suggest --enable-ext when extensions are off."""
    error_code, _, _ = get_main_output(["--validate", get_data("tests/wf/mpi_simple.cwl")])
    output = " ".join(caplog.text.split())
    assert error_code != 0
    assert "Try running again with --enable-ext" in output
    assert "'MPIRequirement'" in output
    assert "mpi_simple.cwl" in output


def test_missing_enable_ext_suggests_flag_for_long_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Find the extension when a long path wraps the validation message."""
    long_dir = tmp_path / ("nested" * 20)
    long_dir.mkdir()
    tool = long_dir / "tool.cwl"
    tool.write_text(Path(get_data("tests/wf/mpi_simple.cwl")).read_text())
    error_code, _, _ = get_main_output(["--validate", str(tool)])
    assert error_code != 0
    assert "Try running again with --enable-ext" in " ".join(caplog.text.split())


def test_unknown_extension_with_enable_ext_has_no_suggestion(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Do not suggest --enable-ext to someone who already provided it."""
    tool = tmp_path / "tool.cwl"
    tool.write_text(
        "cwlVersion: v1.2\n"
        "class: CommandLineTool\n"
        "$namespaces:\n"
        "  cwltool: http://commonwl.org/cwltool#\n"
        "requirements:\n"
        "  cwltool:NoSuchExtension: {}\n"
        "baseCommand: echo\n"
        "inputs: []\n"
        "outputs: []\n"
    )
    error_code, _, _ = get_main_output(["--enable-ext", "--validate", str(tool)])
    output = " ".join(caplog.text.split())
    assert error_code != 0
    assert "cwltool#NoSuchExtension" in output
    assert "Try running again with --enable-ext" not in output


def test_misspelled_requirement_has_no_suggestion(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Do not suggest --enable-ext for a reference that is not an extension."""
    tool = tmp_path / "tool.cwl"
    tool.write_text(
        "cwlVersion: v1.2\n"
        "class: CommandLineTool\n"
        "requirements:\n"
        "  ShelCommandRequirement: {}\n"
        "baseCommand: echo\n"
        "inputs: []\n"
        "outputs: []\n"
    )
    error_code, _, _ = get_main_output(["--validate", str(tool)])
    output = " ".join(caplog.text.split())
    assert error_code != 0
    assert "ShelCommandRequirement" in output
    assert "--enable-ext" not in output


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
    with monkeypatch.context() as m:
        m.setenv("CWLTOOL_OPTIONS", "--enable-ext")
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


def test_ext_in_dollarsign_graph() -> None:
    error_code, stdout, stderr = get_main_output(
        ["--validate", "--enable-ext", get_data("tests/wf/hello_gpu.cwl")]
    )
    assert error_code == 0
