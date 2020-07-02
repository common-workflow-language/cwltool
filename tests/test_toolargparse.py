import argparse
import os
from io import StringIO
from tempfile import NamedTemporaryFile
from typing import Callable

import py.path
import pytest  # type: ignore

import cwltool.executors
from cwltool.argparser import generate_parser
from cwltool.context import LoadingContext
from cwltool.load_tool import load_tool
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


@needs_docker  # type: ignore
@pytest.mark.parametrize("name,script_contents,params", scripts_argparse_params)  # type: ignore
def test_argparse(
    name: str, script_contents: str, params: Callable[[str], str], tmpdir: py.path.local
) -> None:
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


def test_dont_require_inputs() -> None:
    stream = StringIO()

    script = None
    try:
        script = NamedTemporaryFile(mode="w", delete=False)
        script.write(script_a)
        script.close()

        assert (
            main(
                argsl=["--debug", script.name, "--input", script.name],
                executor=cwltool.executors.NoopJobExecutor(),
                stdout=stream,
            )
            == 0
        )
        assert (
            main(
                argsl=["--debug", script.name],
                executor=cwltool.executors.NoopJobExecutor(),
                stdout=stream,
            )
            == 2
        )
        assert (
            main(
                argsl=["--debug", script.name],
                executor=cwltool.executors.NoopJobExecutor(),
                input_required=False,
                stdout=stream,
            )
            == 0
        )

    except SystemExit as err:
        assert err.code == 0, script.name if script else None
    finally:
        if script and script.name and os.path.exists(script.name):
            os.unlink(script.name)


def test_argparser_with_doc() -> None:
    """The `desription` field is set if `doc` field is provided."""
    loadingContext = LoadingContext()
    tool = load_tool(get_data("tests/with_doc.cwl"), loadingContext)
    p = argparse.ArgumentParser()
    parser = generate_parser(p, tool, {}, [], False)
    assert parser.description is not None


def test_argparser_without_doc() -> None:
    """The `desription` field is None if `doc` field is not provided."""
    loadingContext = LoadingContext()
    tool = load_tool(get_data("tests/without_doc.cwl"), loadingContext)
    p = argparse.ArgumentParser()
    parser = generate_parser(p, tool, {}, [], False)
    assert parser.description is None
