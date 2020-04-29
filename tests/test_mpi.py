import sys
import os.path
import pytest
from ruamel import yaml
import json
from .util import get_data, get_main_output

from cwltool.mpi import MpiConfig

def test_mpi_conf_defaults():
    mpi = MpiConfig()
    assert mpi.runner == "mpirun"
    assert mpi.nproc_flag == "-n"
    assert mpi.default_nproc == 1
    assert mpi.extra_flags == []

def test_mpi_conf_unknownkeys():    
    with pytest.raises(ValueError):
        MpiConfig({"runner": "mpiexec", "foo": "bar"})

@pytest.fixture
def fake_mpi_conf(tmpdir):
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
""".format(interpreter=sys.executable)
    mpirun_file = tmpdir.join("fake_mpirun")
    mpirun_file.write(mpirun_text)
    mpirun_file.chmod(0o755)

    plat_conf = {
        "runner": str(mpirun_file),
        "nproc_flag": "--num",
        "extra_flags": ["--no-fail"]
        }
    plat_conf_file = tmpdir.join("plat_mpi.yml")
    plat_conf_file.write(yaml.round_trip_dump(plat_conf))
    yield str(plat_conf_file)
    
def test_fake_mpi_config(fake_mpi_conf):
    conf_obj = MpiConfig.load(fake_mpi_conf)
    runner = conf_obj.runner
    assert os.path.dirname(runner) == os.path.dirname(fake_mpi_conf)
    assert os.path.basename(runner) == "fake_mpirun"
    assert conf_obj.nproc_flag == "--num"
    assert conf_obj.default_nproc == 1
    assert conf_obj.extra_flags == ["--no-fail"]
    
def cwltool_args(fake_mpi_conf):
    return ["--enable-ext", "--enable-dev", "--mpi-config-file", fake_mpi_conf]

def test_simple_mpi_tool(fake_mpi_conf):
    args = cwltool_args(fake_mpi_conf) + [get_data("tests/wf/mpi_simple.cwl")]
    rc, stdout, stderr = get_main_output(args)
    assert rc == 0

    output = json.loads(stdout)
    pid_path = output['pids']['path']
    with open(pid_path) as pidfile:
        pids = [int(line) for line in pidfile]
    assert len(pids) == 2

def make_processes_input(np, tmpdir):
    input_file = os.path.join(tmpdir, "input.yml")
    with open(input_file, "w") as f:
        f.write("processes: %d\n" % np)
    return input_file

def test_simple_mpi_nproc_expr(fake_mpi_conf):
    np = 4
    input_file = make_processes_input(np, os.path.dirname(fake_mpi_conf))

    args = cwltool_args(fake_mpi_conf) + [get_data("tests/wf/mpi_expr.cwl"), input_file]
    rc, stdout, stderr = get_main_output(args)
    assert rc == 0

    output = json.loads(stdout)
    pid_path = output['pids']['path']
    with open(pid_path) as pidfile:
        pids = [int(line) for line in pidfile]
    assert len(pids) == np

def test_mpi_workflow(fake_mpi_conf):
    np = 3
    input_file = make_processes_input(np, os.path.dirname(fake_mpi_conf))

    args = cwltool_args(fake_mpi_conf) + [get_data("tests/wf/mpi_simple_wf.cwl"), input_file]
    rc, stdout, stderr = get_main_output(args)
    assert rc == 0

    output = json.loads(stdout)
    lc_path = output['line_count']['path']
    with open(lc_path) as lc_file:
        lc = int(lc_file.read())
    assert lc == np

