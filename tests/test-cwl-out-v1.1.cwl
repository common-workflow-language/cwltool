class: CommandLineTool
cwlVersion: v1.1

inputs: []

baseCommand: sh

arguments:
   - -c
   - |
     echo foo > foo && echo '{"foo": {"location": "foo", "class": "File"} }'

stdout: cwl.output.json

outputs: {}