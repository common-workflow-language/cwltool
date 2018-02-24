import json
import unittest

import pytest

import cwltool
import cwltool.factory
from cwltool.executors import MultithreadedJobExecutor
from cwltool.utils import onWindows
from .util import get_data


class TestParallel(unittest.TestCase):
    @pytest.mark.skipif(onWindows(),
                        reason="Unexplainable behavior: cwltool on AppVeyor does not recognize cwlVersion"
                               "in count-lines1-wf.cwl")
    def test_sequential_workflow(self):
        test_file = "tests/wf/count-lines1-wf.cwl"
        f = cwltool.factory.Factory(executor=MultithreadedJobExecutor())
        echo = f.make(get_data(test_file))
        self.assertEqual(echo(file1= {
                "class": "File",
                "location": get_data("tests/wf/whale.txt")
            }),
            {"count_output": 16})

    def test_scattered_workflow(self):
        test_file = "tests/wf/scatter-wf4.cwl"
        job_file = "tests/wf/scatter-job2.json"
        f = cwltool.factory.Factory(executor=MultithreadedJobExecutor())
        echo = f.make(get_data(test_file))
        with open(get_data(job_file)) as job:
            self.assertEqual(echo(**json.load(job)), {'out': ['foo one three', 'foo two four']})
