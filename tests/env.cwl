#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs: []
requirements:
  ShellCommandRequirement: {}
baseCommand: echo
arguments:
  - valueFrom: >
      {\\"env_count\\": \$(env | wc -l)}
    shellQuote: False
stdout: cwl.output.json
outputs:
  env_count: int
