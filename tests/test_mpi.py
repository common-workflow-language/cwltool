"""Tests of the experimental MPI extension."""
import json
import os.path
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Generator, List, MutableMapping, Optional, Tuple

import pkg_resources
import pytest
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.avro.schema import Names
from schema_salad.utils import yaml_no_ts

import cwltool.load_tool
import cwltool.singularity
import cwltool.udocker
from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.main import main
from cwltool.mpi import MpiConfig, MPIRequirementName

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

    def run_once(self, args: List[str]):
        subprocess.run(
            args, input=self.indata, stdout=sys.stdout, stderr=sys.stderr
        ).check_returncode()

    def run_many(self, n: int, args: List[str]):
        for i in range(n):
            self.run_once(args)

if __name__ == "__main__":
    args = make_parser().parse_args()
    assert args.no_fail == True, "Didn't set the --no-fail flag"
    r = Runner()
    r.run_many(args.num, args.progargs)
""".format(
        interpreter=sys.executable
    )
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


def cwltool_args(fake_mpi_conf: str) -> List[str]:
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
        monkeypatch.setenv("USER", "tester")
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
    with pkg_resources.resource_stream("cwltool", "extensions-v1.1.yml") as res:
        ext11 = res.read().decode("utf-8")
        cwltool.process.use_custom_schema("v1.1", "http://commonwl.org/cwltool", ext11)
        schema = cwltool.process.get_schema("v1.1")[1]
        assert isinstance(schema, Names)
        yield schema


mpiReq = CommentedMap({"class": MPIRequirementName, "processes": 1})
containerReq = CommentedMap({"class": "DockerRequirement"})
basetool = CommentedMap({"cwlVersion": "v1.1", "inputs": CommentedSeq(), "outputs": CommentedSeq()})


def mk_tool(
    schema: Names,
    opts: List[str],
    reqs: Optional[List[CommentedMap]] = None,
    hints: Optional[List[CommentedMap]] = None,
) -> Tuple[LoadingContext, RuntimeContext, CommentedMap]:
    tool = basetool.copy()

    if reqs is not None:
        tool["requirements"] = CommentedSeq(reqs)
    if hints is not None:
        tool["hints"] = CommentedSeq(hints)

    args = cwltool.argparser.arg_parser().parse_args(opts)
    args.enable_ext = True
    rc = RuntimeContext(vars(args))
    lc = cwltool.main.setup_loadingContext(None, rc, args)
    lc.avsc_names = schema
    return lc, rc, tool


def test_singularity(schema_ext11: Names) -> None:
    lc, rc, tool = mk_tool(schema_ext11, ["--singularity"], reqs=[mpiReq, containerReq])
    clt = CommandLineTool(tool, lc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.singularity.SingularityCommandLineJob


def test_udocker(schema_ext11: Names) -> None:
    lc, rc, tool = mk_tool(schema_ext11, ["--udocker"], reqs=[mpiReq, containerReq])
    clt = CommandLineTool(tool, lc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.udocker.UDockerCommandLineJob


def test_docker_hint(schema_ext11: Names) -> None:
    # Docker hint, MPI required
    lc, rc, tool = mk_tool(schema_ext11, [], hints=[containerReq], reqs=[mpiReq])
    clt = CommandLineTool(tool, lc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.job.CommandLineJob


def test_docker_required(schema_ext11: Names) -> None:
    # Docker required, MPI hinted
    lc, rc, tool = mk_tool(schema_ext11, [], reqs=[containerReq], hints=[mpiReq])
    clt = CommandLineTool(tool, lc)
    jr = clt.make_job_runner(rc)
    assert jr is cwltool.docker.DockerCommandLineJob


def test_docker_mpi_both_required(schema_ext11: Names) -> None:
    # Both required - error
    with pytest.raises(cwltool.errors.UnsupportedRequirement):
        lc, rc, tool = mk_tool(schema_ext11, [], reqs=[mpiReq, containerReq])
        clt = CommandLineTool(tool, lc)
        clt.make_job_runner(rc)


def test_docker_mpi_both_hinted(schema_ext11: Names) -> None:
    # Both hinted - error
    with pytest.raises(cwltool.errors.UnsupportedRequirement):
        lc, rc, tool = mk_tool(schema_ext11, [], hints=[mpiReq, containerReq])
        clt = CommandLineTool(tool, lc)
        clt.make_job_runner(rc)
