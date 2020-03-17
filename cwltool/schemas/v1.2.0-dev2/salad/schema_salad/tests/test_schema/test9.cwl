#!/usr/bin/env cwl-runner
class: Workflow
inputs:
  foo: string
outputs:
  bar: string
steps:
  step1:
    scatterMethod: 12
    in: []
    out: [out]
