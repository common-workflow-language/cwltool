from __future__ import absolute_import
import unittest
import pytest
from tempfile import NamedTemporaryFile

from .util import needs_docker
from cwltool.main import main


class ToolArgparse(unittest.TestCase):
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
    def test_spaces_in_input_files(self):
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.script)
            f.flush()
            f.close()
            with NamedTemporaryFile(prefix="test with spaces", delete=False) as spaces:
                spaces.close()
                self.assertEquals(
                    main(["--debug", f.name, '--input', spaces.name]), 1)
                self.assertEquals(
                    main(["--debug", "--relax-path-checks", f.name, '--input',
                          spaces.name]), 0)


if __name__ == '__main__':
    unittest.main()
