import os
import sys
from io import BytesIO, StringIO
from tempfile import NamedTemporaryFile

import pytest

import cwltool.executors
from cwltool.main import main

from .util import get_data, needs_docker

script_a = """
#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
doc: "This tool is developed for SMC-RNA Challenge for detecting gene fusions (STAR fusion)"
inputs:
  #Give it a list of input files
  - id: input
    type: File
    inputBinding:
      position: 0
outputs:
  - id: output
    type: File
    outputBinding:
      glob: test.txt
stdout: test.txt
baseCommand: [cat]
"""

script_b = """
#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  - id: bdg
    type: "boolean"
outputs:
  - id: output
    type: File
    outputBinding:
      glob: foo
baseCommand:
  - echo
  - "ff"
stdout: foo
"""

script_c = """
#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: ExpressionTool

inputs:
  foo:
    type:
      type: record
      fields:
        one: File
        two: string

expression: $(inputs.foo.two)

outputs: []
"""

scripts_argparse_params = [
    ("help", script_a, lambda x: ["--debug", x, "--input", get_data("tests/echo.cwl")]),
    ("boolean", script_b, lambda x: [x, "--help"]),
    ("help with c", script_c, lambda x: [x, "--help"]),
    (
        "foo with c",
        script_c,
        lambda x: [x, "--foo.one", get_data("tests/echo.cwl"), "--foo.two", "test"],
    ),
]


@needs_docker
@pytest.mark.parametrize("name,script_contents,params", scripts_argparse_params)
def test_argparse(name, script_contents, params, tmpdir):
    script = None
    try:
        script = NamedTemporaryFile(mode="w", delete=False)
        script.write(script_contents)
        script.close()

        my_params = ["--outdir", str(tmpdir)]
        my_params.extend(params(script.name))
        assert main(my_params) == 0, name

    except SystemExit as err:
        assert err.code == 0, name
    finally:
        if script and script.name and os.path.exists(script.name):
            os.unlink(script.name)


class NoopJobExecutor(cwltool.executors.JobExecutor):
    def run_jobs(
        self,
        process,  # type: Process
        job_order_object,  # type: Dict[str, Any]
        logger,  # type: logging.Logger
        runtime_context,  # type: RuntimeContext
    ):  # type: (...) -> None
        pass

    def execute(
        self,
        process,  # type: Process
        job_order_object,  # type: Dict[str, Any]
        runtime_context,  # type: RuntimeContext
        logger=None,  # type: logging.Logger
    ):  # type: (...) -> Tuple[Optional[Union[Dict[str, Any], List[Dict[str, Any]]]], str]
        return {}, "success"


def test_dont_require_inputs():
    if sys.version_info[0] < 3:
        stream = BytesIO()
    else:
        stream = StringIO()

    script = None
    try:
        script = NamedTemporaryFile(mode="w", delete=False)
        script.write(script_a)
        script.close()

        assert (
            main(
                argsl=["--debug", script.name, "--input", script.name],
                executor=NoopJobExecutor(),
                stdout=stream,
            )
            == 0
        )
        assert (
            main(
                argsl=["--debug", script.name],
                executor=NoopJobExecutor(),
                stdout=stream,
            )
            == 2
        )
        assert (
            main(
                argsl=["--debug", script.name],
                executor=NoopJobExecutor(),
                input_required=False,
                stdout=stream,
            )
            == 0
        )

    except SystemExit as err:
        assert err.code == 0, name
    finally:
        if script and script.name and os.path.exists(script.name):
            os.unlink(script.name)
