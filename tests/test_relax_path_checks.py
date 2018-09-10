import os
from tempfile import NamedTemporaryFile

from cwltool.main import main

from .util import needs_docker


script = '''
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
'''

@needs_docker
def test_spaces_in_input_files():
    try:
        script_file = NamedTemporaryFile(mode='w', delete=False)
        script_file.write(script)
        script_file.flush()
        script_file.close()

        spaces = NamedTemporaryFile(prefix="test with spaces", delete=False)
        spaces.close()

        params = ["--debug", script_file.name, '--input', spaces.name]
        assert main(params) == 1
        assert main(["--relax-path-checks"] + params) == 0
    finally:
        os.remove(script_file.name)
        os.remove(spaces.name)
