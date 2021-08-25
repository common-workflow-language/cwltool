from pathlib import Path

import pytest

from cwltool.main import main

from .util import needs_docker

script = """
#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  - id: input
    type: File
    inputBinding:
      position: 0
  - id: output
    type: string
outputs:
  - id: output
    type: File
    outputBinding:
      glob: "$(inputs.output)"
stdout: "$(inputs.output)"
baseCommand: [cat]
"""


@needs_docker
def test_spaces_in_input_files(tmp_path: Path) -> None:
    script_name = tmp_path / "script"
    spaces = tmp_path / "test with spaces"
    spaces.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(spaces),
        "--output",
        "test.txt",
    ]
    assert main(params) == 1
    assert main(["--relax-path-checks"] + params) == 0


@needs_docker
@pytest.mark.parametrize(
    "filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان", "abc+DEFGZ.z_12345-"]
)
def test_unicode_in_input_files(tmp_path: Path, filename: str) -> None:
    script_name = tmp_path / "script"
    inputfile = tmp_path / filename
    inputfile.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(inputfile),
        "--output",
        "test.txt",
    ]
    assert main(params) == 0


@needs_docker
@pytest.mark.parametrize(
    "filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان", "abc+DEFGZ.z_12345-"]
)
def test_unicode_in_output_files(tmp_path: Path, filename: str) -> None:
    script_name = tmp_path / "script"
    inputfile = tmp_path / "test"
    inputfile.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(inputfile),
        "--output",
        filename,
    ]
    assert main(params) == 0
