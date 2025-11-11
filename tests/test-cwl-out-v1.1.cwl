class: CommandLineTool
cwlVersion: v1.1

inputs: []

baseCommand: sh

arguments:
   - -c
   - |
     echo '{"foo": 5 }'

stdout: cwl.output.json

outputs: {}