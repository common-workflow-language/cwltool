#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  - id: inp
    type: string
    inputBinding: {}
outputs:
  out:
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
  stdout:
    type: stdout
baseCommand: echo
stdout: out.txt
