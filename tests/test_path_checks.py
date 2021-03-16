import os
import pytest
from tempfile import NamedTemporaryFile

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
def test_spaces_in_input_files(tmpdir):
    try:
        script_file = NamedTemporaryFile(mode="w", delete=False)
        script_file.write(script)
        script_file.flush()
        script_file.close()

        spaces = NamedTemporaryFile(prefix="test with spaces", delete=False)
        spaces.close()

        params = [
            "--debug",
            "--outdir",
            str(tmpdir),
            script_file.name,
            "--input",
            spaces.name,
            "--output",
            "test.txt",
        ]
        assert main(params) == 1
        assert main(["--relax-path-checks"] + params) == 0
    finally:
        os.remove(script_file.name)
        os.remove(spaces.name)


@needs_docker
@pytest.mark.parametrize("filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان"])
def test_unicode_in_input_files(tmpdir, filename):
    try:
        script_file = NamedTemporaryFile(mode="w", delete=False)
        script_file.write(script)
        script_file.flush()
        script_file.close()

        inputfile = NamedTemporaryFile(prefix=filename, delete=False)
        inputfile.close()

        params = [
            "--debug",
            "--outdir",
            str(tmpdir),
            script_file.name,
            "--input",
            inputfile.name,
            "--output",
            "test.txt",
        ]
        assert main(params) == 0
    finally:
        os.remove(script_file.name)
        os.remove(inputfile.name)


@needs_docker
@pytest.mark.parametrize("filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان"])
def test_unicode_in_output_files(tmpdir, filename):
    try:
        script_file = NamedTemporaryFile(mode="w", delete=False)
        script_file.write(script)
        script_file.flush()
        script_file.close()

        inputfile = NamedTemporaryFile(prefix="test", delete=False)
        inputfile.close()

        params = [
            "--debug",
            "--outdir",
            str(tmpdir),
            script_file.name,
            "--input",
            inputfile.name,
            "--output",
            filename,
        ]
        assert main(params) == 0
    finally:
        os.remove(script_file.name)
        os.remove(inputfile.name)
