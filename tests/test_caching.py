import re
from pathlib import Path

import pytest

from .util import get_data, get_main_output, needs_docker

test_factors = [(""), ("--parallel"), ("--debug"), ("--parallel --debug")]


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_wf_without_container(tmp_path: Path, factor: str) -> None:
    """Confirm that we can run a workflow without a container."""
    test_file = "hello-workflow.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(
        [
            "--cachedir",
            cache_dir,
            "--outdir",
            str(tmp_path / "outdir"),
            get_data("tests/wf/" + test_file),
            "--usermessage",
            "hello",
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_issue_740_fixed(tmp_path: Path, factor: str) -> None:
    """Confirm that re-running a particular workflow with caching succeeds."""
    test_file = "cache_test_workflow.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0

    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Output of job will be cached in" not in stderr
    assert error_code == 0, stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cache_relative_paths(tmp_path: Path, factor: str) -> None:
    """Confirm that re-running a particular workflow with caching succeeds."""
    test_file = "secondary-files.cwl"
    test_job_file = "secondary-files-job.yml"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(
        [
            "--out",
            str(tmp_path / "out"),
            "--cachedir",
            cache_dir,
            get_data(f"tests/{test_file}"),
            get_data(f"tests/{test_job_file}"),
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0

    commands = factor.split()
    commands.extend(
        [
            "--out",
            str(tmp_path / "out2"),
            "--cachedir",
            cache_dir,
            get_data(f"tests/{test_file}"),
            get_data(f"tests/{test_job_file}"),
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Output of job will be cached in" not in stderr
    assert error_code == 0, stderr

    assert (tmp_path / "cwltool_cache" / "27903451fc1ee10c148a0bdeb845b2cf").exists()


@pytest.mark.parametrize("factor", test_factors)
def test_cache_default_literal_file(tmp_path: Path, factor: str) -> None:
    """Confirm that running a CLT with a default literal file with caching succeeds."""
    test_file = "tests/wf/extract_region_specs.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(
        [
            "--out",
            str(tmp_path / "out"),
            "--cachedir",
            cache_dir,
            get_data(test_file),
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cache_dockerreq_hint_instead_of_req(tmp_path: Path, factor: str) -> None:
    """The cache must not be checked when there is an invalid use of an absolute path in iwdr.listing."""
    cache_dir = str(tmp_path / "cwltool_cache")
    test_job_file = "tests/wf/loadContents-input.yml"
    # First, run the iwd-container-entryname1 conformance tests with caching turned on
    test1_file = "tests/wf/iwd-container-entryname1.cwl"
    commands1 = factor.split()
    commands1.extend(
        [
            "--out",
            str(tmp_path / "out1"),
            "--cachedir",
            cache_dir,
            get_data(test1_file),
            get_data(test_job_file),
        ]
    )
    error_code1, _, stderr1 = get_main_output(commands1)

    stderr1 = re.sub(r"\s\s+", " ", stderr1)
    assert "completed success" in stderr1
    assert error_code1 == 0
    # Second, run the iwd-container-entryname3 test, which should fail
    # even though it would be a cache hit, except that its DockerRequirement is
    # in `hints` instead of `requirements` and one of the initial working directory
    # items has an absolute path starting with `/`.
    test2_file = "tests/wf/iwd-container-entryname3.cwl"
    commands2 = factor.split()
    commands2.extend(
        [
            "--out",
            str(tmp_path / "out2"),
            "--cachedir",
            cache_dir,
            get_data(test2_file),
            get_data(test_job_file),
        ]
    )
    error_code2, _, stderr2 = get_main_output(commands2)

    stderr2 = re.sub(r"\s\s+", " ", stderr2)
    assert (
        "at index 0 of listing is invalid, name can only start with '/' "
        "when DockerRequirement is in 'requirements" in stderr2
    )
    assert error_code2 == 1
