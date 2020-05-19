import sys
import os.path
from io import StringIO
import pytest
from ruamel import yaml
import json
from .util import get_data, working_directory, windows_needs_docker

from cwltool.mpi import MpiConfig
from cwltool.main import main


def test_mpi_conf_defaults():
    mpi = MpiConfig()
    assert mpi.runner == "mpirun"
    assert mpi.nproc_flag == "-n"
    assert mpi.default_nproc == 1
    assert mpi.extra_flags == []
    assert mpi.env_pass == []
    assert mpi.env_set == {}


def test_mpi_conf_unknownkeys():
    with pytest.raises(ValueError):
        MpiConfig({"runner": "mpiexec", "foo": "bar"})


@pytest.fixture(scope="class")
def fake_mpi_conf(tmp_path_factory):
    """Make a super simple mpirun-alike for applications that don't actually use MPI.
    It just runs the command multiple times (in serial).

    Then create a plaform MPI config YAML file that should make it work
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
    plat_conf_file.write_text(yaml.round_trip_dump(plat_conf))

    yield str(plat_conf_file)

    plat_conf_file.unlink()
    mpirun_file.unlink()
    mpitmp.rmdir()


def make_processes_input(np, tmp_path):
    input_file = tmp_path / "input.yml"
    with input_file.open("w") as f:
        f.write("processes: %d\n" % np)
    return input_file


def cwltool_args(fake_mpi_conf):
    return ["--enable-ext", "--enable-dev", "--mpi-config-file", fake_mpi_conf]


class TestMpiRun:
    def test_fake_mpi_config(self, fake_mpi_conf):
        conf_obj = MpiConfig.load(fake_mpi_conf)
        runner = conf_obj.runner
        assert os.path.dirname(runner) == os.path.dirname(fake_mpi_conf)
        assert os.path.basename(runner) == "fake_mpirun"
        assert conf_obj.nproc_flag == "--num"
        assert conf_obj.default_nproc == 1
        assert conf_obj.extra_flags == ["--no-fail"]

    @windows_needs_docker
    def test_simple_mpi_tool(self, fake_mpi_conf, tmp_path):
        stdout = StringIO()
        stderr = StringIO()
        with working_directory(tmp_path):
            rc = main(
                argsl=cwltool_args(fake_mpi_conf)
                + [get_data("tests/wf/mpi_simple.cwl")],
                stdout=stdout,
                stderr=stderr,
            )
            assert rc == 0

            output = json.loads(stdout.getvalue())
            pid_path = output["pids"]["path"]
            with open(pid_path) as pidfile:
                pids = [int(line) for line in pidfile]
            assert len(pids) == 2

    @windows_needs_docker
    def test_simple_mpi_nproc_expr(self, fake_mpi_conf, tmp_path):
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

    @windows_needs_docker
    def test_mpi_workflow(self, fake_mpi_conf, tmp_path):
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

    @windows_needs_docker
    def test_environment(self, fake_mpi_conf, tmp_path):
        stdout = StringIO()
        stderr = StringIO()
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
            assert e["USER"] == os.environ["USER"]
            assert e["TEST_MPI_FOO"] == "bar"
