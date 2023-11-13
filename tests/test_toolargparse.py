import argparse
from io import StringIO
from pathlib import Path
from typing import Callable, List

import pytest

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

script_d = """
#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: ExpressionTool

inputs:
  foo:
    type:
      - type: enum
        symbols: [cymbal1, cymbal2]

expression: $(inputs.foo)

outputs: []
"""

script_e = """
#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: ExpressionTool

inputs:
  foo: File

expression: '{"bar": $(inputs.foo.location)}'

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
    (
        "foo with d",
        script_d,
        lambda x: [x, "--foo", "cymbal2"],
    ),
    (
        "foo with e",
        script_e,
        lambda x: [x, "--foo", "http://example.com"],
    ),
]


@needs_docker
@pytest.mark.parametrize("name,script_contents,params", scripts_argparse_params)
def test_argparse(
    name: str, script_contents: str, params: Callable[[str], str], tmp_path: Path
) -> None:
    script_name = tmp_path / "script"
    try:
        with script_name.open(mode="w") as script:
            script.write(script_contents)

        my_params = ["--outdir", str(tmp_path / "outdir"), "--debug"]
        my_params.extend(params(script.name))
        assert main(my_params) == 0, name

    except SystemExit as err:
        assert err.code == 0, name


def test_dont_require_inputs(tmp_path: Path) -> None:
    stream = StringIO()

    script_name = tmp_path / "script"
    try:
        with script_name.open(mode="w") as script:
            script.write(script_a)

        assert (
            main(
                argsl=["--debug", str(script_name), "--input", str(script_name)],
                executor=cwltool.executors.NoopJobExecutor(),
                stdout=stream,
            )
            == 0
        )
        assert (
            main(
                argsl=["--debug", str(script_name)],
                executor=cwltool.executors.NoopJobExecutor(),
                stdout=stream,
            )
            == 2
        )
        assert (
            main(
                argsl=["--debug", str(script_name)],
                executor=cwltool.executors.NoopJobExecutor(),
                input_required=False,
                stdout=stream,
            )
            == 0
        )

    except SystemExit as err:
        assert err.code == 0, script_name if script else None


def test_argparser_with_doc() -> None:
    """The `description` field is set if `doc` field is provided."""
    loadingContext = LoadingContext()
    tool = load_tool(get_data("tests/with_doc.cwl"), loadingContext)
    p = argparse.ArgumentParser()
    parser = generate_parser(p, tool, {}, [], False)
    assert parser.description is not None


def test_argparser_without_doc() -> None:
    """The `description` field is None if `doc` field is not provided."""
    loadingContext = LoadingContext()
    tool = load_tool(get_data("tests/without_doc.cwl"), loadingContext)
    p = argparse.ArgumentParser()
    parser = generate_parser(p, tool, {}, [], False)
    assert parser.description is None


@pytest.mark.parametrize(
    "job_order,expected_values",
    [
        # no arguments, so we expect the default value
        ([], ["/home/bart/cwl_test/test1"]),
        # arguments, provided, one or many, meaning that the default value is not expected
        (["--file_paths", "/home/bart/cwl_test/test2"], ["/home/bart/cwl_test/test2"]),
        (
            [
                "--file_paths",
                "/home/bart/cwl_test/test2",
                "--file_paths",
                "/home/bart/cwl_test/test3",
            ],
            ["/home/bart/cwl_test/test2", "/home/bart/cwl_test/test3"],
        ),
    ],
)
def test_argparse_append_with_default(job_order: List[str], expected_values: List[str]) -> None:
    """
    Confirm that the appended arguments must not include the default.

    But if no appended argument, then the default is used.
    """
    loadingContext = LoadingContext()
    tool = load_tool(get_data("tests/default_values_list.cwl"), loadingContext)
    toolparser = generate_parser(argparse.ArgumentParser(prog="test"), tool, {}, [], False)
    cmd_line = vars(toolparser.parse_args(job_order))
    file_paths = list(cmd_line["file_paths"])
    assert expected_values == file_paths
