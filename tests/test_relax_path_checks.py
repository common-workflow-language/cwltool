import unittest
from tempfile import NamedTemporaryFile

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

    def test_spaces_in_input_files(self):
        with NamedTemporaryFile() as f:
            f.write(self.script)
            f.flush()
            with NamedTemporaryFile(prefix="test with spaces") as spaces:
                self.assertEquals(
                    main(["--debug", f.name, '--input', spaces.name]), 1)
                self.assertEquals(
                    main(["--debug", "--relax-path-checks", f.name, '--input',
                          spaces.name]), 0)


if __name__ == '__main__':
    unittest.main()
