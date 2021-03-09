import os
from pathlib import Path

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
outputs:
  - id: output
    type: File
    outputBinding:
      glob: test.txt
stdout: test.txt
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
    ]
    assert main(params) == 1
    assert main(["--relax-path-checks"] + params) == 0
