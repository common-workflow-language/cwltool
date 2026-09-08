"""Tests of the experimental MPI extension."""

import json
import os.path
import sys
import tempfile
from collections.abc import Generator, MutableMapping
from importlib.resources import files
from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
from cwl_utils.types import CWLOutputType
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.avro import schema
from schema_salad.avro.schema import Names
from schema_salad.ref_resolver import file_uri
from schema_salad.utils import yaml_no_ts

import cwltool.load_tool
import cwltool.singularity
import cwltool.udocker
from cwltool.builder import Builder
from cwltool.command_line_tool import CommandLineTool
from cwltool.context import RuntimeContext
from cwltool.main import main
from cwltool.mpi import MpiConfig, MPIRequirementName
from cwltool.stdfsaccess import StdFsAccess
from cwltool.update import INTERNAL_VERSION
from .util import get_data, working_directory


def test_mpi_conf_defaults() -> None:
    mpi = MpiConfig()
    assert mpi.runner == "mpirun"
    assert mpi.nproc_flag == "-n"
    assert mpi.default_nproc == 1
    assert mpi.extra_flags == []
    assert mpi.env_pass == []
    assert mpi.env_pass_regex == []
    assert mpi.env_set == {}
    assert mpi.shm_dir == "/dev/shm"
    assert mpi.shm_enabled is True


def test_mpi_conf_unknownkeys() -> None:
    with pytest.raises(TypeError):
        MpiConfig(runner="mpiexec", foo="bar")  # type: ignore


@pytest.fixture(scope="class")
def fake_mpi_conf(tmp_path_factory: Any) -> Generator[str, None, None]:
    """
    Make a super simple mpirun-alike for applications that don't actually use MPI.

    It just runs the command multiple times (in serial).

    Then create a platform MPI config YAML file that should make it work
    for the testing examples.
    """
    mpirun_text = """#!{interpreter}
import argparse
import sys
import subprocess
from io import StringIO
from typing import List

def make_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--num", type=int, help="number of times to run the application")
    p.add_argument(
        "--no-fail", help="add this flag to actually work", action="store_true"
    )
    p.add_argument(
        "progargs", nargs=argparse.REMAINDER, help="The program and its arguments"
    )
    return p

class Runner:
    def __init__(self):
        if sys.stdin.isatty():
            self.indata = None
        else:
            self.indata = sys.stdin.read().encode(sys.stdin.encoding)

    def run_once(self, args: list[str]):
        subprocess.run(
            args, input=self.indata, stdout=sys.stdout, stderr=sys.stderr
        ).check_returncode()

    def run_many(self, n: int, args: list[str]):
        for i in range(n):
            self.run_once(args)

if __name__ == "__main__":
    args = make_parser().parse_args()
    assert args.no_fail == True, "Didn't set the --no-fail flag"
    r = Runner()
    r.run_many(args.num, args.progargs)
""".format(interpreter=sys.executable)
    mpitmp = tmp_path_factory.mktemp("fake_mpi")
    mpirun_file = mpitmp / "fake_mpirun"
    mpirun_file.write_text(mpirun_text)
    mpirun_file.chmod(0o755)

    plat_conf = {
        "runner": str(mpirun_file),
        "nproc_flag": "--num",
        "extra_flags": ["--no-fail"],
        "env_set": {"TEST_MPI_FOO": "bar"},
        "env_pass": ["USER"],
    }
    plat_conf_file = mpitmp / "plat_mpi.yml"
    yaml = yaml_no_ts()
    yaml.dump(plat_conf, plat_conf_file)

    yield str(plat_conf_file)

    plat_conf_file.unlink()
    mpirun_file.unlink()
    mpitmp.rmdir()


def make_processes_input(np: int, tmp_path: Path) -> Path:
    input_file = tmp_path / "input.yml"
    with input_file.open("w") as f:
        f.write("processes: %d\n" % np)
    return input_file


def cwltool_args(fake_mpi_conf: str) -> list[str]:
    return ["--enable-ext", "--enable-dev", "--mpi-config-file", fake_mpi_conf]


class TestMpiRun:
    def test_fake_mpi_config(self, fake_mpi_conf: str) -> None:
        conf_obj = MpiConfig.load(fake_mpi_conf)
        runner = conf_obj.runner
        assert os.path.dirname(runner) == os.path.dirname(fake_mpi_conf)
        assert os.path.basename(runner) == "fake_mpirun"
        assert conf_obj.nproc_flag == "--num"
        assert conf_obj.default_nproc == 1
        assert conf_obj.extra_flags == ["--no-fail"]

    def test_simple_mpi_tool(self, fake_mpi_conf: str, tmp_path: Path) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with working_directory(tmp_path):
            rc = main(
                argsl=cwltool_args(fake_mpi_conf) + [get_data("tests/wf/mpi_simple.cwl")],
                stdout=stdout,
                stderr=stderr,
            )
            assert rc == 0

            output = json.loads(stdout.getvalue())
            pid_path = output["pids"]["path"]
            with open(pid_path) as pidfile:
                pids = [int(line) for line in pidfile]
            assert len(pids) == 2

    def test_simple_mpi_nproc_expr(self, fake_mpi_conf: str, tmp_path: Path) -> None:
        np = 4
        input_file = make_processes_input(np, tmp_path)
        stdout = StringIO()
        stderr = StringIO()
        with working_directory(tmp_path):
            rc = main(
                argsl=cwltool_args(fake_mpi_conf)
                + [get_data("tests/wf/mpi_expr.cwl"), str(input_file)],
                stdout=stdout,
                stderr=stderr,
            )
            assert rc == 0

            output = json.loads(stdout.getvalue())
            pid_path = output["pids"]["path"]
            with open(pid_path) as pidfile:
                pids = [int(line) for line in pidfile]
            assert len(pids) == np

    def test_mpi_workflow(self, fake_mpi_conf: str, tmp_path: Path) -> None:
        np = 3
        input_file = make_processes_input(np, tmp_path)
        stdout = StringIO()
        stderr = StringIO()
        with working_directory(tmp_path):
            rc = main(
                argsl=cwltool_args(fake_mpi_conf)
                + [get_data("tests/wf/mpi_simple_wf.cwl"), str(input_file)],
                stdout=stdout,
                stderr=stderr,
            )
            assert rc == 0

            output = json.loads(stdout.getvalue())
            lc_path = output["line_count"]["path"]
            with open(lc_path) as lc_file:
                lc = int(lc_file.read())
                assert lc == np

    def test_environment(
        self, fake_mpi_conf: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with monkeypatch.context() as m:
            m.setenv("USER", "tester")
            with working_directory(tmp_path):
                rc = main(
                    argsl=cwltool_args(fake_mpi_conf) + [get_data("tests/wf/mpi_env.cwl")],
                    stdout=stdout,
                    stderr=stderr,
                )
                assert rc == 0

                output = json.loads(stdout.getvalue())
                env_path = output["environment"]["path"]
                with open(env_path) as envfile:
                    e = {}
                    for line in envfile:
                        k, v = line.strip().split("=", 1)
                        e[k] = v
                assert e["USER"] == "tester"
                assert e["TEST_MPI_FOO"] == "bar"


def test_env_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm that MPI extension passes environment variables correctly."""
    config = MpiConfig(
        env_pass=["A", "B", "LONG_NAME"],
        env_pass_regex=["TOOLNAME", "MPI_.*_CONF"],
    )

    env: MutableMapping[str, str] = {}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {})
        env = {}
        config.pass_through_env_vars(env)
        assert env == {}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"A": "a"})
        env = {}
        config.pass_through_env_vars(env)
        assert env == {"A": "a"}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"A": "a", "C": "c"})
        env = {}
        config.pass_through_env_vars(env)
        assert env == {"A": "a"}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"A": "a", "B": "b", "C": "c"})
        env = {"PATH": "one:two:three", "HOME": "/tmp/dir", "TMPDIR": "/tmp/dir"}
        config.pass_through_env_vars(env)
        assert env == {
            "PATH": "one:two:three",
            "HOME": "/tmp/dir",
            "TMPDIR": "/tmp/dir",
            "A": "a",
            "B": "b",
        }

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"TOOLNAME": "foobar"})
        env = {}
        config.pass_through_env_vars(env)
        assert env == {"TOOLNAME": "foobar"}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"_TOOLNAME_": "foobar"})
        env = {}
        config.pass_through_env_vars(env)
        # Cos we are matching not searching
        assert env == {}

    with monkeypatch.context() as m:
        m.setattr(os, "environ", {"MPI_A_CONF": "A", "MPI_B_CONF": "B"})

        env = {}
        config.pass_through_env_vars(env)
        # Cos we are matching not searching
        assert env == {"MPI_A_CONF": "A", "MPI_B_CONF": "B"}


# Reading the schema is super slow - cache for the session
@pytest.fixture(scope="session")
def schema_ext11() -> Generator[Names, None, None]:
    ext11 = files("cwltool").joinpath("extensions-v1.1.yml").read_text("utf-8")
    cwltool.process.use_custom_schema("v1.1", "http://commonwl.org/cwltool", ext11)
    schema = cwltool.process.get_schema("v1.1")[1]
    assert isinstance(schema, Names)
    yield schema


mpiReq = CommentedMap({"class": MPIRequirementName, "processes": 1})
containerReq = CommentedMap({"class": "DockerRequirement"})
basetool = CommentedMap(
    {
        "cwlVersion": "v1.1",
        "class": "CommandLineTool",
        "inputs": CommentedSeq(),
        "outputs": CommentedSeq(),
    }
)


def mk_tool(
    schema: Names,
    opts: list[str],
    reqs: list[CommentedMap] | None = None,
    hints: list[CommentedMap] | None = None,
) -> tuple[RuntimeContext, CommandLineTool]:
    tool = basetool.copy()

    if reqs is not None:
        tool["requirements"] = CommentedSeq(reqs)
    if hints is not None:
        tool["hints"] = CommentedSeq(hints)

    args = cwltool.argparser.arg_parser().parse_args(opts)
    args.enable_ext = True
    args.basedir = os.path.dirname(os.path.abspath("."))
    rc = RuntimeContext(vars(args))
    lc = cwltool.main.setup_loadingContext(None, rc, args)
    lc.avsc_names = schema
    tool["id"] = file_uri(os.path.abspath("./mktool.cwl"))
    assert lc.loader is not None
    lc.loader.idx[tool["id"]] = tool
    return rc, cast(CommandLineTool, cwltool.load_tool.load_tool(tool, lc))


def test_singularity(schema_ext11: Names) -> None:
    rc, clt = mk_tool(schema_ext11, ["--singularity"], reqs=[mpiReq, containerReq])
    clt._init_job({}, rc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.singularity.SingularityCommandLineJob


def _make_fake_singularity() -> str:
    tmpdir = tempfile.mkdtemp()
    fake_path = Path(tmpdir) / "singularity"
    with open(fake_path, "w") as f:
        f.write("#!/bin/sh\n")
        # It must print the version, as another test calls ``version()``.
        f.write("echo 'singularity-ce version 3.11.5'\n")

    fake_path.chmod(0o755)

    return tmpdir


@pytest.mark.parametrize(
    "requirements,shm_enabled,shm_dir,expected_command",
    [
        ([], True, "/dev/shm", "singularity"),
        ([], False, "/dev/shm", "singularity"),
        (
            [CommentedMap({"class": MPIRequirementName, "processes": 1})],
            True,
            "/dev/shm",
            "singularity_wrapper.sh",
        ),
        (
            [CommentedMap({"class": MPIRequirementName, "processes": 1})],
            False,
            "/dev/shm",
            "singularity_wrapper.sh",
        ),
    ],
    ids=[
        "No requirements, runs singularity, no shared mem used",
        "No requirements, runs singularity, no shared mem used",
        "MPIRequirement, runs mpirun, shared memory used",
        "MPIRequirement, but no shared memory volume used",
    ],
)
def test_singularity_create_runtime(
    requirements: list[MutableMapping[str, CWLOutputType | None]],
    shm_enabled: bool,
    shm_dir: str,
    expected_command: str,
    schema_ext11: Names,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests that"""
    runtime_context = RuntimeContext({})
    runtime_context.mpi_config.shm_dir = shm_dir
    runtime_context.mpi_config.shm_enabled = shm_enabled
    builder = Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        requirements,
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
    job = cwltool.singularity.SingularityCommandLineJob(
        builder, {}, CommandLineTool.make_path_mapper, requirements=requirements, hints=[], name=""
    )
    env = dict(os.environ)
    # Inject a fake singularity into the $PATH. The reason for this, is that
    # the MacOS GitHub Actions job fails when ``job.create_runtime`` gets
    # called. Internally, it calls ``is_apptainer_1_1_or_newer``, which uses
    # ``version_output = check_output(["singularity", "--version"], text=True).strip()``.
    # The command call above will raise an exception (below) and crash pytest.
    # ``FileNotFoundError: [Errno 2] No such file or directory: 'singularity'``.
    fake_bin_dir = _make_fake_singularity()
    with monkeypatch.context() as m:
        m.setenv("PATH", fake_bin_dir + os.pathsep + os.environ["PATH"])
        env["PATH"] = fake_bin_dir + os.pathsep + env["PATH"]

        job.prepare_environment(runtime_context, env)
        command, options = job.create_runtime(env, runtime_context)

        assert command
        assert not options

        assert command[0] == expected_command or command[0].endswith(expected_command)

        mpi_req, is_req = builder.get_requirement(MPIRequirementName)

        def any_contains(haystack: list[str], needle: str) -> bool:
            return any(needle in h for h in haystack)

        shared_memory_used = any_contains(command, shm_dir)

        if mpi_req and is_req:
            if shm_enabled:
                assert shared_memory_used, "Missing shared memory volume!"
            else:
                assert not shared_memory_used, "Shared memory volume not supposed to be used!"
        else:
            assert not shared_memory_used, "Shared memory volume used without MPIRequirement!"


def test_udocker(schema_ext11: Names) -> None:
    rc, clt = mk_tool(schema_ext11, ["--udocker"], reqs=[mpiReq, containerReq])
    clt._init_job({}, rc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.udocker.UDockerCommandLineJob


def test_docker_hint(schema_ext11: Names) -> None:
    # Docker hint, MPI required
    rc, clt = mk_tool(schema_ext11, [], hints=[containerReq], reqs=[mpiReq])
    clt._init_job({}, rc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.job.CommandLineJob


def test_docker_required(schema_ext11: Names) -> None:
    # Docker required, MPI hinted
    rc, clt = mk_tool(schema_ext11, [], reqs=[containerReq], hints=[mpiReq])
    clt._init_job({}, rc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.docker.DockerCommandLineJob


def test_docker_mpi_both_required(schema_ext11: Names) -> None:
    # Both required - error
    rc, clt = mk_tool(schema_ext11, [], reqs=[mpiReq, containerReq])
    with pytest.raises(cwltool.errors.UnsupportedRequirement):
        clt._init_job({}, rc)
    clt.make_job_runner(rc)


def test_docker_mpi_both_hinted(schema_ext11: Names) -> None:
    # Both hinted - error
    rc, clt = mk_tool(schema_ext11, [], hints=[mpiReq, containerReq])
    with pytest.raises(cwltool.errors.UnsupportedRequirement):
        clt._init_job({}, rc)
    clt.make_job_runner(rc)
