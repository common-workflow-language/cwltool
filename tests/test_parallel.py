import json
import time
from pathlib import Path

from cwltool.context import RuntimeContext
from cwltool.executors import MultithreadedJobExecutor
from cwltool.factory import Factory, WorkflowStatus

from .util import get_data, needs_docker


@needs_docker
def test_sequential_workflow(tmp_path: Path) -> None:
    test_file = "tests/wf/count-lines1-wf.cwl"
    executor = MultithreadedJobExecutor()
    runtime_context = RuntimeContext()
    runtime_context.outdir = str(tmp_path)
    runtime_context.select_resources = executor.select_resources
    factory = Factory(executor, None, runtime_context)
    echo = factory.make(get_data(test_file))
    file_contents = {"class": "File", "location": get_data("tests/wf/whale.txt")}
    assert echo(file1=file_contents) == {"count_output": 16}


@needs_docker
def test_scattered_workflow() -> None:
    test_file = "tests/wf/scatter-wf4.cwl"
    job_file = "tests/wf/scatter-job2.json"
    factory = Factory(MultithreadedJobExecutor())
    echo = factory.make(get_data(test_file))
    with open(get_data(job_file)) as job:
        assert echo(**json.load(job)) == {"out": ["foo one three", "foo two four"]}


def test_on_error_kill() -> None:
    test_file = "tests/wf/on-error_kill.cwl"
    runtime_context = RuntimeContext()
    runtime_context.on_error = "kill"
    factory = Factory(MultithreadedJobExecutor(), None, runtime_context)
    ks_test = factory.make(get_data(test_file))

    # arbitrary test values
    sleep_time = 33  # a "sufficiently large" timeout
    n_sleepers = 5

    try:
        start_time = time.time()
        ks_test(sleep_time=sleep_time)
    except WorkflowStatus as e:
        assert e.out == {"instructed_sleep_times": [sleep_time] * n_sleepers}
        assert time.time() - start_time < sleep_time
