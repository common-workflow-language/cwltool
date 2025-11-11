class: CommandLineTool
cwlVersion: v1.2

inputs: []

baseCommand: sh

arguments:
   - -c
   - |
     echo '{"foo": 5 }'

stdout: cwl.output.json

outputs: {}