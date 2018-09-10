import os
from tempfile import NamedTemporaryFile

import pytest
from cwltool.main import main

from .util import get_data, needs_docker


script_a = '''
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

script_b = '''
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

script_c = '''
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

scripts_argparse_params = [
    ('help', script_a,
     lambda x: ["--debug", x, '--input', get_data('tests/echo.cwl')]
     ),
    ('boolean', script_b, lambda x: [x, '--help']
     ),
]

@needs_docker
@pytest.mark.parametrize('name,script_contents,params', scripts_argparse_params)
def test_argparse(name, script_contents, params):
    try:
        script = NamedTemporaryFile(mode='w', delete=False)
        script.write(script_contents)
        script.flush()
        script.close()

        try:
            assert main(params(script.name)) == 0, name
        except SystemExit as err:
            assert err.code == 0, name
    finally:
        if os.path.exists(script.name):
            os.remove(script.name)

script_c_params = [
    (lambda x: [x, '--help']),
    (lambda x: [x, '--foo.one', get_data('tests/echo.cwl'), '--foo.two', 'test'])
]

@pytest.mark.parametrize('params', script_c_params)
def test_argparse_record(params):
    try:
        script = NamedTemporaryFile(mode='w', delete=False)
        script.write(script_c)
        script.flush()
        script.close()

        try:
            assert main(params(script.name)) == 0
        except SystemExit as err:
            assert err.code == 0
    finally:
        if os.path.exists(script.name):
            os.remove(script.name)
