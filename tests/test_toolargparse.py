import unittest
from tempfile import NamedTemporaryFile
from testfixtures import TempDirectory
from cwltool.main import main
import os


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

    def test_leave_tmpdir_prefix(self):
        with TempDirectory() as d:
            with NamedTemporaryFile() as f:
                f.write(self.script)
                f.flush()
                try:
                    import random
                    indicator_str = 'test%.6f' % random.random()
                    self.assertEquals(main(['--leave-tmpdir', '--tmpdir-prefix', d.path + "/" + indicator_str,
                                            f.name, '--input', 'README.rst']), 0)
                    self.assertTrue([d for d in os.listdir(d.path) if d.startswith(indicator_str)])
                except SystemExit as e:
                    self.assertEquals(e.code, 0)

    def test_rm_tmpdir_prefix(self):
        with TempDirectory() as d:
            with NamedTemporaryFile() as f:
                f.write(self.script)
                f.flush()
                try:
                    import random
                    indicator_str = 'test%.6f' % random.random()
                    self.assertEquals(main(['--tmpdir-prefix', d.path + "/" + indicator_str,
                                            f.name, '--input', 'README.rst']), 0)
                    self.assertFalse([d for d in os.listdir(d.path) if d.startswith(indicator_str)])
                except SystemExit as e:
                    self.assertEquals(e.code, 0)

    def test_leave_tmp_outdir_prefix(self):
        with TempDirectory() as d:
            with NamedTemporaryFile() as f:
                f.write(self.script)
                f.flush()
                try:
                    import random
                    indicator_str = 'test%.6f' % random.random()
                    self.assertEquals(main(['--leave-outputs', '--tmp-outdir-prefix', d.path + "/" + indicator_str,
                                            f.name, '--input', 'README.rst']), 0)
                    self.assertTrue([d for d in os.listdir(d.path) if d.startswith(indicator_str)])
                except SystemExit as e:
                    self.assertEquals(e.code, 0)

    def test_rm_tmp_outdir_prefix(self):
        with TempDirectory() as d:
            with NamedTemporaryFile() as f:
                f.write(self.script)
                f.flush()
                try:
                    import random
                    indicator_str = 'test%.6f' % random.random()
                    self.assertEquals(main(['--tmp-outdir-prefix', d.path + "/" + indicator_str,
                                            f.name, '--input', 'README.rst']), 0)
                    self.assertFalse([d for d in os.listdir(d.path) if d.startswith(indicator_str)])
                except SystemExit as e:
                    self.assertEquals(e.code, 0)
