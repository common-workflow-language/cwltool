#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
inputs: []
outputs:
  b:
    type: string
    outputSource: step2/c
steps:
  step1:
    in: []
    out: [c]
    run:
      class: CommandLineTool
      id: subtool
      inputs: []
      outputs:
        b:
          type: string
          outputBinding:
            outputEval: "qq"
      baseCommand: echo
  step2:
    in:
      a: step1/c
    out: [c]
    run:
      class: CommandLineTool
      id: subtool
      inputs:
        a: string
      outputs:
        b: string
      baseCommand: echo