class: CommandLineTool
cwlVersion: v1.0
inputs:
  in: string
outputs:
  value: string

baseCommand: ["/bin/bash", "-c", 'echo {\"value\": \"$TEST_ENV\"}']

stdout: cwl.output.json
