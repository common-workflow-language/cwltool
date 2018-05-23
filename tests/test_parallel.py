import json
import unittest

import pytest

import cwltool
import cwltool.factory
from cwltool.executors import MultithreadedJobExecutor
from cwltool.utils import onWindows
from .util import get_data, get_windows_safe_factory, windows_needs_docker


class TestParallel(unittest.TestCase):
    @windows_needs_docker
    def test_sequential_workflow(self):
        test_file = "tests/wf/count-lines1-wf.cwl"
        f = get_windows_safe_factory(executor=MultithreadedJobExecutor())
        echo = f.make(get_data(test_file))
        self.assertEqual(echo(file1= {
                "class": "File",
                "location": get_data("tests/wf/whale.txt")
            }),
            {"count_output": 16})

    @windows_needs_docker
    def test_scattered_workflow(self):
        test_file = "tests/wf/scatter-wf4.cwl"
        job_file = "tests/wf/scatter-job2.json"
        f = get_windows_safe_factory(executor=MultithreadedJobExecutor())
        echo = f.make(get_data(test_file))
        with open(get_data(job_file)) as job:
            self.assertEqual(echo(**json.load(job)), {'out': ['foo one three', 'foo two four']})
