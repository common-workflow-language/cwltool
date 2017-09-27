from __future__ import absolute_import
import unittest
import pytest
from tempfile import NamedTemporaryFile

from cwltool.main import main
from cwltool.utils import onWindows

from .util import get_data

class ToolArgparse(unittest.TestCase):
    script = '''
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

    script2 = '''
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

    script3 = '''
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
'''

    @pytest.mark.skipif(onWindows(),
                        reason="Instance of Cwltool is used, On windows that invoke a default docker Container")
    def test_help(self):
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.script)
            f.flush()
            f.close()
            self.assertEquals(main(["--debug", f.name, '--input',
                get_data('tests/echo.cwl')]), 0)
            self.assertEquals(main(["--debug", f.name, '--input',
                get_data('tests/echo.cwl')]), 0)


    @pytest.mark.skipif(onWindows(),
                        reason="Instance of Cwltool is used, On windows that invoke a default docker Container")
    def test_bool(self):
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.script2)
            f.flush()
            f.close()
            try:
                self.assertEquals(main([f.name, '--help']), 0)
            except SystemExit as e:
                self.assertEquals(e.code, 0)

    def test_record_help(self):
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.script3)
            f.flush()
            f.close()
            try:
                self.assertEquals(main([f.name, '--help']), 0)
            except SystemExit as e:
                self.assertEquals(e.code, 0)

    def test_record(self):
        with NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(self.script3)
            f.flush()
            f.close()
            try:
                self.assertEquals(main([f.name, '--foo.one',
                    get_data('tests/echo.cwl'), '--foo.two', 'test']), 0)
            except SystemExit as e:
                self.assertEquals(e.code, 0)


if __name__ == '__main__':
    unittest.main()
