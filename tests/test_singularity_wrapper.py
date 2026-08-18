"""Tests for the Shell wrapper of the Singularity command.

This script tests a Shell script. This script does not contribute to the
project test coverage (although kcov, or bats+kcov could be used in the
future).
"""

import os
import subprocess
from importlib.resources import files
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "args,expected_return_code",
    [(["--help"], 1), ([""], 1), (["singularity"], 1)],
    ids=[
        "Print usage because user passed --help",
        "Print usage because of missing args",
        "Print usage because not all args provided",
    ],
)
def test_wrapper_usage(args: list[str], expected_return_code: int) -> None:
    """Test the usage of the Singularity wrapper is printed."""
    wrapper = str(files("cwltool") / "singularity_wrapper.sh")
    command: list[str] = [wrapper] + args
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == expected_return_code
    assert "Wrapper around Singularity/Apptainer for CWL + MPI + Singularity" in result.stderr


def test_wrapper_invalid_baseline_env_file() -> None:
    """Test the script fails if the given file is not valid."""
    wrapper = str(files("cwltool") / "singularity_wrapper.sh")
    command: list[str] = [wrapper, "parangaricutirimicuaro.dat", "foo"]
    result = subprocess.run(command, capture_output=True, text=True)

    assert result.returncode == 2
    assert "file not found" in result.stderr


def test_wrapper_env_vars(tmp_path: "Path") -> None:
    """Test that the wrapper script adds the new environment variables."""
    fake_singularity = tmp_path / "fake_singularity"
    fake_singularity.write_text(dedent("""\
    #!/bin/bash
    echo "Fake Singularity script"
    env
    """))
    fake_singularity.chmod(0o755)

    new_env_var = "TEST_WRAPPER_ENV_VARS_INJECTED_VAR"

    # Create the baseline environment variables file.
    baseline_env = os.environ
    assert new_env_var not in baseline_env, "The test needs a new env var!"
    baseline = tmp_path / "baseline.env"
    baseline.write_text("A=1\nB=2\n")
    for k, v in baseline_env.items():
        baseline.write_text(f"{k}={v}")

    # Now pretend we are mpirun, and we are adding a new env var.
    new_env = os.environ.copy()
    new_env[new_env_var] = "42"

    wrapper = str(files("cwltool") / "singularity_wrapper.sh")
    command: list[str] = [wrapper, str(baseline), str(fake_singularity), "--cleanenv"]

    result = subprocess.run(command, capture_output=True, text=True, env=new_env)

    assert result.returncode == 0
    # There, now the wrapper just runs `env`, and the output must
    # contain the new environment variable. We know the wrapper
    # must have worked because we have thew new variable in the
    # output...
    assert new_env_var in result.stdout
    # And also because we have the new SINGULARITYENV_{new_env_var}!
    assert f"SINGULARITYENV_{new_env_var}" in result.stdout
