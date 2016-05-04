import unittest
from tempfile import NamedTemporaryFile
from cwltool.main import main


class ToolArgparse(unittest.TestCase):


    script='''
#!/usr/bin/env cwl-runner
cwlVersion: "cwl:draft-3"
class: CommandLineTool
description: "This tool is developed for SMC-RNA Challenge for detecting gene fusions (STAR fusion)"
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

    def test_help(self):
        with NamedTemporaryFile() as f:
            f.write(self.script)
            f.flush()
            self.assertEquals(main([f.name, '--input', 'README.rst']), 0)
