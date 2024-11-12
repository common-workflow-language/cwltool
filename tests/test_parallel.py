import json
import math
import time
from pathlib import Path
from typing import Union, cast

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

    def selectResources(
        request: dict[str, Union[int, float]], _: RuntimeContext
    ) -> dict[str, Union[int, float]]:
        # Remove the "one job per core" resource constraint so that
        # parallel jobs aren't withheld on machines with few cores
        return {
            "cores": 0,
            "ram": math.ceil(request["ramMin"]),  # default
            "tmpdirSize": math.ceil(request["tmpdirMin"]),  # default
            "outdirSize": math.ceil(request["outdirMin"]),  # default
        }

    runtime_context = RuntimeContext()
    runtime_context.on_error = "kill"
    runtime_context.select_resources = selectResources
    factory = Factory(MultithreadedJobExecutor(), None, runtime_context)
    ks_test = factory.make(get_data(test_file))

    # arbitrary test values
    sleep_time = 3333  # a "sufficiently large" timeout
    n_sleepers = 4
    start_time = 0.0

    try:
        start_time = time.time()
        ks_test(
            sleep_time=sleep_time,
            n_sleepers=n_sleepers,
        )
    except WorkflowStatus as e:
        end_time = time.time()
        output = cast(dict[str, list[bool]], e.out)["roulette_mask"]
        assert len(output) == n_sleepers and sum(output) == 1
        assert end_time - start_time < sleep_time
