#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.1
inputs: []
outputs:
  a:
    type: int
    outputSource: step3/output
  b:
    type: int
    outputSource: step4/output
steps:
  step1:
    in:
      in: {default: "3"}
    out: [out]
    run: echo-file-tool.cwl
  step2:
    in:
      r: step1/out
    out: [out]
    run: updateval_inplace.cwl
  step3:
    in:
      file1: step1/out
      wait: step2/out
    out: [output]
    run: parseInt-tool.cwl
  step4:
    in:
      file1: step2/out
    out: [output]
    run: parseInt-tool.cwl
