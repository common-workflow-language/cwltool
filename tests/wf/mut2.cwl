#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
inputs:
  a: File
outputs:
  out:
    type: File
    outputSource: step2/out
steps:
  step1:
    in:
      r: a
    out: [out]
    run: updateval_inplace.cwl
  step2:
    in:
      r: step1/out
    out: [out]
    run: updateval_inplace.cwl
