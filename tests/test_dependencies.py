"""Tests of satisfying SoftwareRequirement via dependencies."""
import os
import tempfile
from getpass import getuser
from pathlib import Path
from shutil import which
from types import ModuleType
from typing import Optional, Tuple

import pytest

from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
from cwltool.software_requirements import get_container_from_software_requirements

from .util import get_data, get_main_output, get_tool_env, needs_docker

deps: Optional[ModuleType] = None
try:
    from galaxy.tool_util import deps  # type: ignore[no-redef]
except ImportError:
    pass


@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-tool-util is not installed")
def test_biocontainers(tmp_path: Path) -> None:
    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, _ = get_main_output(
        [
            "--outdir",
            str(tmp_path / "out"),
            "--beta-use-biocontainers",
            "--beta-dependencies-directory",
            str(tmp_path / "deps"),
            wflow,
            job,
        ]
    )

    assert error_code == 0


@needs_docker
@pytest.mark.skipif(not deps, reason="galaxy-tool-util is not installed")
def test_biocontainers_resolution(tmp_path: Path) -> None:
    """Confirm expected container name for --beta-use-biocontainers."""
    tool = load_tool(get_data("tests/seqtk_seq.cwl"), LoadingContext())
    assert (
        get_container_from_software_requirements(
            True, tool, container_image_cache_path=str(tmp_path)
        )
        == "quay.io/biocontainers/seqtk:r93--0"
    )


@pytest.fixture(scope="session")
def bioconda_setup(request: pytest.FixtureRequest) -> Tuple[Optional[int], str]:
    """
    Caches the conda environment created for seqtk_seq.cwl.

    Respects ``--basetemp`` via code copied from
    :py:method:`pytest.TempPathFactory.getbasetemp`.
    """

    assert request.config.cache
    deps_dir = request.config.cache.get("bioconda_deps", None)
    if deps_dir is not None and not Path(deps_dir).exists():
        # cache value set, but cache is gone :( ... recreate
        deps_dir = None

    if deps_dir is None:
        given_basetemp = request.config.option.basetemp
        if given_basetemp is not None:
            basetemp = Path(os.path.abspath(str(given_basetemp))).resolve()
            deps_dir = basetemp / "bioconda"
        else:
            from_env = os.environ.get("PYTEST_DEBUG_TEMPROOT")
            temproot = Path(from_env or tempfile.gettempdir()).resolve()
            rootdir = temproot.joinpath(f"pytest-of-{getuser() or 'unknown'}")
            try:
                rootdir.mkdir(mode=0o700, exist_ok=True)
            except OSError:
                rootdir = temproot.joinpath("pytest-of-unknown")
                rootdir.mkdir(mode=0o700, exist_ok=True)
            deps_dir = rootdir / "bioconda"
        request.config.cache.set("bioconda_deps", str(deps_dir))

    deps_dirpath = Path(deps_dir)
    deps_dirpath.mkdir(parents=True, exist_ok=True)

    wflow = get_data("tests/seqtk_seq.cwl")
    job = get_data("tests/seqtk_seq_job.json")
    error_code, _, stderr = get_main_output(
        [
            "--outdir",
            str(deps_dirpath / "out"),
            "--beta-conda-dependencies",
            "--beta-dependencies-directory",
            str(deps_dirpath / "deps"),
            "--debug",
            wflow,
            job,
        ]
    )
    return error_code, stderr


@pytest.mark.skipif(not deps, reason="galaxy-tool-util is not installed")
def test_bioconda(bioconda_setup: Tuple[Optional[int], str]) -> None:
    error_code, stderr = bioconda_setup
    assert error_code == 0, stderr


@pytest.mark.skipif(not deps, reason="galaxy-tool-util is not installed")
@pytest.mark.skipif(not which("modulecmd"), reason="modulecmd not installed")
def test_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Do a basic smoke test using environment modules to satisfy a SoftwareRequirement."""
    wflow = get_data("tests/random_lines.cwl")
    job = get_data("tests/random_lines_job.json")
    monkeypatch.setenv("MODULEPATH", os.path.join(os.getcwd(), "tests/test_deps_env/modulefiles"))
    error_code, _, stderr = get_main_output(
        [
            "--outdir",
            str(tmp_path / "out"),
            "--beta-dependency-resolvers-configuration",
            "--beta-dependencies-directory",
            str(tmp_path / "deps"),
            "tests/test_deps_env_modules_resolvers_conf.yml",
            "--debug",
            wflow,
            job,
        ]
    )

    assert error_code == 0, stderr


@pytest.mark.skipif(not deps, reason="galaxy-tool-util is not installed")
@pytest.mark.skipif(not which("modulecmd"), reason="modulecmd not installed")
def test_modules_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Check that the environment variables set by a module are being propagated correctly.

    Do so by  by running `env` as the tool and parsing its output.
    """
    monkeypatch.setenv("MODULEPATH", os.path.join(os.getcwd(), "tests/test_deps_env/modulefiles"))
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
