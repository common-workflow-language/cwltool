#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
inputs:
  a: File
outputs: []
steps:
  step1:
    in:
      r: a
    out: []
    run: updateval_inplace.cwl
  step2:
    in:
      r: a
    out: []
    run: updateval_inplace.cwl
