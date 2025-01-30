#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
inputs:
  in: string
outputs:
  value: string

baseCommand: ["/bin/bash", "-c", 'echo {\"value\": \"$TEST_ENV\"}']

stdout: cwl.output.json
