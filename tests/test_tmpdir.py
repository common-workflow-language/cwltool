"""Test that all temporary directories respect the --tmpdir-prefix and --tmp-outdir-prefix options."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, cast

import pytest
from ruamel.yaml.comments import CommentedMap
from schema_salad.avro import schema
from schema_salad.sourceline import cmap

from cwltool.builder import Builder
from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.docker import DockerCommandLineJob
from cwltool.job import JobBase
from cwltool.main import main
from cwltool.pathmapper import MapperEnt
from cwltool.singularity import SingularityCommandLineJob
from cwltool.stdfsaccess import StdFsAccess
from cwltool.update import INTERNAL_VERSION, ORIGINAL_CWLVERSION
from cwltool.utils import create_tmp_dir

from .util import get_data, get_main_output, needs_docker, needs_singularity


def test_docker_commandLineTool_job_tmpdir_prefix(tmp_path: Path) -> None:
    """Test that docker enabled CommandLineTool respects temp directory directives."""
    loading_context = LoadingContext(
        {
            "metadata": {
                "cwlVersion": INTERNAL_VERSION,
                ORIGINAL_CWLVERSION: INTERNAL_VERSION,
            }
        }
    )
    clt = CommandLineTool(
        cast(
            CommentedMap,
            cmap(
                {
                    "cwlVersion": INTERNAL_VERSION,
                    "class": "CommandLineTool",
                    "inputs": [],
                    "outputs": [],
                    "requirements": [
                        {
                            "class": "DockerRequirement",
                            "dockerPull": "docker.io/debian:stable-slim",
                        }
                    ],
                }
            ),
        ),
        loading_context,
    )
    tmpdir_prefix = str(tmp_path / "1")
    tmp_outdir_prefix = str(tmp_path / "2")
    runtime_context = RuntimeContext(
        {
            "tmpdir_prefix": tmpdir_prefix,
            "tmp_outdir_prefix": tmp_outdir_prefix,
        }
    )
    job = next(clt.job({}, None, runtime_context))
    assert isinstance(job, JobBase)
    assert job.stagedir and job.stagedir.startswith(tmpdir_prefix)
    assert job.tmpdir and job.tmpdir.startswith(tmpdir_prefix)
    assert job.outdir and job.outdir.startswith(tmp_outdir_prefix)


def test_commandLineTool_job_tmpdir_prefix(tmp_path: Path) -> None:
    """Test that non-docker enabled CommandLineTool respects temp directory directives."""
    loading_context = LoadingContext(
        {
            "metadata": {
                "cwlVersion": INTERNAL_VERSION,
                ORIGINAL_CWLVERSION: INTERNAL_VERSION,
            }
        }
    )
    clt = CommandLineTool(
        cast(
            CommentedMap,
            cmap(
                {
                    "cwlVersion": INTERNAL_VERSION,
                    "class": "CommandLineTool",
                    "inputs": [],
                    "outputs": [],
                    "requirements": [],
                }
            ),
        ),
        loading_context,
    )
    tmpdir_prefix = str(tmp_path / "1")
    tmp_outdir_prefix = str(tmp_path / "2")
    runtime_context = RuntimeContext(
        {
            "tmpdir_prefix": tmpdir_prefix,
            "tmp_outdir_prefix": tmp_outdir_prefix,
        }
    )
    job = next(clt.job({}, None, runtime_context))
    assert isinstance(job, JobBase)
    assert job.stagedir and job.stagedir.startswith(tmpdir_prefix)
    assert job.tmpdir and job.tmpdir.startswith(tmpdir_prefix)
    assert job.outdir and job.outdir.startswith(tmp_outdir_prefix)


@needs_docker
def test_dockerfile_tmpdir_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that DockerCommandLineJob.get_image respects temp directory directives."""
    monkeypatch.setattr(target=subprocess, name="check_call", value=lambda *args, **kwargs: True)
    (tmp_path / "out").mkdir()
    tmp_outdir_prefix = tmp_path / "out" / "1"
    (tmp_path / "3").mkdir()
    tmpdir_prefix = str(tmp_path / "3" / "ttmp")
    runtime_context = RuntimeContext(
        {"tmpdir_prefix": tmpdir_prefix, "user_space_docker_cmd": None}
    )
    builder = Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        [],
        [],
        {},
        None,
        None,
        StdFsAccess,
        StdFsAccess(""),
        None,
        0.1,
        False,
        False,
        False,
        "no_listing",
        runtime_context.get_outdir(),
        runtime_context.get_tmpdir(),
        runtime_context.get_stagedir(),
        INTERNAL_VERSION,
        "docker",
    )
    assert DockerCommandLineJob(
        builder, {}, CommandLineTool.make_path_mapper, [], [], ""
    ).get_image(
        {
            "class": "DockerRequirement",
            "dockerFile": "FROM debian:stable-slim",
            "dockerImageId": sys._getframe().f_code.co_name,
        },
        pull_image=True,
        force_pull=True,
        tmp_outdir_prefix=str(tmp_outdir_prefix),
    )
    children = sorted(tmp_outdir_prefix.parent.glob("*"))
    assert len(children) == 1
    subdir = tmp_path / children[0]
    assert len(sorted(subdir.glob("*"))) == 1
    assert (subdir / "Dockerfile").exists()


@needs_docker
def test_dockerfile_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that DockerCommandLineJob.get_image builds a Dockerfile."""
    (tmp_path / "out").mkdir()
    tmp_outdir_prefix = tmp_path / "out" / "1"
    (tmp_path / "3").mkdir()
    tmpdir_prefix = str(tmp_path / "3" / "ttmp")
    runtime_context = RuntimeContext(
        {"tmpdir_prefix": tmpdir_prefix, "user_space_docker_cmd": None}
    )
    builder = Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        [],
        [],
        {},
        None,
        None,
        StdFsAccess,
        StdFsAccess(""),
        None,
        0.1,
        False,
        False,
        False,
        "no_listing",
        runtime_context.get_outdir(),
        runtime_context.get_tmpdir(),
        runtime_context.get_stagedir(),
        INTERNAL_VERSION,
        "docker",
    )

    docker_image_id = sys._getframe().f_code.co_name

    assert DockerCommandLineJob(
        builder, {}, CommandLineTool.make_path_mapper, [], [], ""
    ).get_image(
        {
            "class": "DockerRequirement",
            "dockerFile": "FROM debian:stable-slim",
            "dockerImageId": docker_image_id,
        },
        pull_image=False,
        force_pull=False,
        tmp_outdir_prefix=str(tmp_outdir_prefix),
    )
    output = subprocess.check_output(
        ["docker", "images", "--quiet", docker_image_id], stderr=subprocess.STDOUT, text=True
    )

    # If the output is empty, the image doesn't exist
    assert output.strip(), f"Docker image {docker_image_id} does not exist"


@needs_singularity
def test_dockerfile_singularity_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that SingularityCommandLineJob.get_image builds a Dockerfile with Singularity."""
    tmppath = Path(os.environ.get("APPTAINER_TMPDIR", tmp_path))
    # some HPC not allowed to execute on /tmp so allow user to define temp path with APPTAINER_TMPDIR
    # FATAL:   Unable to create build: 'noexec' mount option set on /tmp, temporary root filesystem
    monkeypatch.setattr(target=subprocess, name="check_call", value=lambda *args, **kwargs: True)
    (tmppath / "out").mkdir(exist_ok=True)
    tmp_outdir_prefix = tmppath / "out" / "1"
    (tmppath / "3").mkdir(exist_ok=True)
    tmpdir_prefix = str(tmppath / "3" / "ttmp")
    runtime_context = RuntimeContext(
        {"tmpdir_prefix": tmpdir_prefix, "user_space_docker_cmd": None}
    )
    builder = Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        [],
        [],
        {},
        None,
        None,
        StdFsAccess,
        StdFsAccess(""),
        None,
        0.1,
        True,
        False,
        False,
        "no_listing",
        runtime_context.get_outdir(),
        runtime_context.get_tmpdir(),
        runtime_context.get_stagedir(),
        INTERNAL_VERSION,
        "singularity",
    )

    assert SingularityCommandLineJob(
        builder, {}, CommandLineTool.make_path_mapper, [], [], ""
    ).get_image(
        {
            "class": "DockerRequirement",
            "dockerFile": "FROM debian:stable-slim",
        },
        pull_image=True,
        tmp_outdir_prefix=str(tmp_outdir_prefix),
        force_pull=True,
    )
    children = sorted(tmp_outdir_prefix.parent.glob("*"))
    subdir = tmppath / children[0]
    children = sorted(subdir.glob("*.sif"))
    image_path = children[0]
    assert image_path.exists()
    shutil.rmtree(subdir)


def test_docker_tmpdir_prefix(tmp_path: Path) -> None:
    """Test that DockerCommandLineJob respects temp directory directives."""
    (tmp_path / "3").mkdir()
    tmpdir_prefix = str(tmp_path / "3" / "ttmp")
    runtime_context = RuntimeContext(
        {"tmpdir_prefix": tmpdir_prefix, "user_space_docker_cmd": None}
    )
    builder = Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        [],
        [],
        {},
        None,
        None,
        StdFsAccess,
        StdFsAccess(""),
        None,
        0.1,
        False,
        False,
        False,
        "no_listing",
        runtime_context.get_outdir(),
        runtime_context.get_tmpdir(),
        runtime_context.get_stagedir(),
        INTERNAL_VERSION,
        "docker",
    )
    job = DockerCommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    runtime: List[str] = []

    volume_writable_file = MapperEnt(
        resolved=get_data("tests/2.fastq"), target="foo", type=None, staged=None
    )
    (tmp_path / "1").mkdir()
    job.add_writable_file_volume(
        runtime, volume_writable_file, None, str(tmp_path / "1" / "writable_file")
    )
    children = sorted((tmp_path / "1").glob("*"))
    assert len(children) == 1
    subdir = tmp_path / children[0]
    assert subdir.name.startswith("writable_file")
    assert len(sorted(subdir.glob("*"))) == 1
    assert (subdir / "2.fastq").exists()

    resolved_writable_dir = tmp_path / "data_orig"
    resolved_writable_dir.mkdir(parents=True)
    volume_dir = MapperEnt(
        resolved=str(resolved_writable_dir), target="bar", type=None, staged=None
    )
    (tmp_path / "2").mkdir()
    job.add_writable_directory_volume(runtime, volume_dir, None, str(tmp_path / "2" / "dir"))
    children = sorted((tmp_path / "2").glob("*"))
    assert len(children) == 1
    subdir = tmp_path / "2" / children[0]
    assert subdir.name.startswith("dir")
    assert len(sorted(subdir.glob("*"))) == 1
    assert (subdir / "data_orig").exists()

    cidfile = job.create_runtime({}, runtime_context)[1]
    assert cidfile and cidfile.startswith(tmpdir_prefix)

    volume_file = MapperEnt(resolved="Hoopla!", target="baz", type=None, staged=None)
    (tmp_path / "4").mkdir()
    job.create_file_and_add_volume(runtime, volume_file, None, None, str(tmp_path / "4" / "file"))
    children = sorted((tmp_path / "4").glob("*"))
    assert len(children) == 1
    subdir = tmp_path / "4" / children[0]
    assert subdir.name.startswith("file")
    assert len(sorted(subdir.glob("*"))) == 1
    assert (subdir / "baz").exists()


def test_runtimeContext_respects_tmpdir_prefix(tmp_path: Path) -> None:
    """Test that RuntimeContext helper methods respects tmpdir_prefix."""
    tmpdir_prefix = str(tmp_path / "foo")
    runtime_context = RuntimeContext({"tmpdir_prefix": tmpdir_prefix})
    assert runtime_context.get_tmpdir().startswith(tmpdir_prefix)
    assert runtime_context.get_stagedir().startswith(tmpdir_prefix)
    assert runtime_context.create_tmpdir().startswith(tmpdir_prefix)
    assert create_tmp_dir(tmpdir_prefix).startswith(tmpdir_prefix)


def test_runtimeContext_respects_tmp_outdir_prefix(tmp_path: Path) -> None:
    """Test that RuntimeContext helper methods respects tmp_outdir_prefix."""
    tmpdir_prefix = str(tmp_path / "foo")
    runtime_context = RuntimeContext({"tmp_outdir_prefix": tmpdir_prefix})
    assert runtime_context.get_outdir().startswith(tmpdir_prefix)
    assert runtime_context.create_outdir().startswith(tmpdir_prefix)


def test_remove_tmpdirs(tmp_path: Path) -> None:
    """Test that the tmpdirs are removed after the job execution."""
    assert (
        main(
            [
                "--tmpdir-prefix",
                str(f"{tmp_path}/"),
                get_data("tests/wf/hello_single_tool.cwl"),
                "--message",
                "Hello",
            ]
        )
        == 0
    )
    assert len(list(tmp_path.iterdir())) == 0


def test_leave_tmpdirs(tmp_path: Path) -> None:
    """Test that the tmpdirs including input staging directories are retained after the job execution."""
    error_code, stdout, stderr = get_main_output(
        [
            "--debug",
            "--tmpdir-prefix",
            str(f"{tmp_path}/tmp/"),
            "--leave-tmpdir",
            "--outdir",
            str(f"{tmp_path}/out/"),
            get_data("tests/env4.cwl"),
        ]
    )
    assert error_code == 0
    assert re.search(rf"\"{re.escape(str(tmp_path))}/tmp/.*/env0\.py\"", stderr)
    assert len(list((tmp_path / "tmp").iterdir())) == 3
    assert len(list((tmp_path / "tmp").glob("**/env0.py"))) == 1
