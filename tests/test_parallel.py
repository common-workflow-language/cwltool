import json

from cwltool.context import RuntimeContext
from cwltool.executors import MultithreadedJobExecutor

from .util import get_data, get_windows_safe_factory, windows_needs_docker


@windows_needs_docker
def test_sequential_workflow():
    test_file = "tests/wf/count-lines1-wf.cwl"
    executor = MultithreadedJobExecutor()
    runtime_context = RuntimeContext()
    runtime_context.select_resources = executor.select_resources
    factory = get_windows_safe_factory(
        executor=executor, runtime_context=runtime_context)
    echo = factory.make(get_data(test_file))
    file_contents = {"class": "File",
                     "location": get_data("tests/wf/whale.txt")}
    assert  echo(file1=file_contents) == {"count_output": 16}

@windows_needs_docker
def test_scattered_workflow():
    test_file = "tests/wf/scatter-wf4.cwl"
    job_file = "tests/wf/scatter-job2.json"
    factory = get_windows_safe_factory(executor=MultithreadedJobExecutor())
    echo = factory.make(get_data(test_file))
    with open(get_data(job_file)) as job:
        assert echo(**json.load(job)) == {'out': ['foo one three', 'foo two four']}
