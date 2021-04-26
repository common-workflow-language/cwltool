"""Tests of satisfying SoftwareRequirement via dependencies."""
import os
from pathlib import Path
from shutil import which
from types import ModuleType
from typing import Dict, List, Optional

import pytest

from cwltool.main import main

from .util import (
    get_data,
    get_main_output,
    get_tool_env,
    needs_docker,
    working_directory,
)

deps = None  # type: Optional[ModuleType]
try:
    from galaxy.tool_util import deps
except ImportError:
    pass


@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_biocontainers() -> None:
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, _ = get_main_output(["--beta-use-biocontainers", wflow, job])

    assert error_code == 0


@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
def test_bioconda() -> None:
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        ["--beta-conda-dependencies", "--debug", wflow, job]
    )

    assert error_code == 0, stderr


@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
@pytest.mark.skipif(not which("modulecmd"), reason="modulecmd not installed")
def test_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do a basic smoke test using environment modules to satisfy a SoftwareRequirement."""
    wflow = get_data("tests/random_lines.cwl")
    job = get_data("tests/random_lines_job.json")
    monkeypatch.setenv(
        "MODULEPATH", os.path.join(os.getcwd(), "tests/test_deps_env/modulefiles")
    )
    error_code, _, stderr = get_main_output(
        [
            "--beta-dependency-resolvers-configuration",
            "tests/test_deps_env_modules_resolvers_conf.yml",
            "--debug",
            wflow,
            job,
        ]
    )

    assert error_code == 0, stderr


@pytest.mark.skipif(not deps, reason="galaxy-lib is not installed")
@pytest.mark.skipif(not which("modulecmd"), reason="modulecmd not installed")
def test_modules_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Check that the environment variables set by a module are being propagated correctly.

    Do so by  by running `env` as the tool and parsing its output.
    """
    monkeypatch.setenv(
        "MODULEPATH", os.path.join(os.getcwd(), "tests/test_deps_env/modulefiles")
    )
    tool_env = get_tool_env(
        tmp_path,
        [
            "--beta-dependency-resolvers-configuration",
            get_data("tests/test_deps_env_modules_resolvers_conf.yml"),
        ],
        get_data("tests/env_with_software_req.yml"),
    )

    assert tool_env["TEST_VAR_MODULE"] == "environment variable ends in space "
    tool_path = tool_env["PATH"].split(":")
    assert get_data("tests/test_deps_env/random-lines/1.0/scripts") in tool_path
