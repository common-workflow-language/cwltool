import unittest
from tempfile import NamedTemporaryFile
from cwltool.main import main


class ToolArgparse(unittest.TestCase):


    script='''
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
'''

    script2='''
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
'''

    def test_help(self):
        with NamedTemporaryFile() as f:
            f.write(self.script)
            f.flush()
            self.assertEquals(main(["--debug", f.name, '--input', 'README.rst']), 0)
            self.assertEquals(main(["--debug", f.name, '--input', 'README.rst']), 0)

    def test_bool(self):
        with NamedTemporaryFile() as f:
            f.write(self.script2)
            f.flush()
            try:
                self.assertEquals(main([f.name, '--help']), 0)
            except SystemExit as e:
                self.assertEquals(e.code, 0)
