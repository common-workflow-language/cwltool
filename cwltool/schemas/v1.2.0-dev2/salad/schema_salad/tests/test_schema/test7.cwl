#!/usr/bin/env cwl-runner
class: Workflow
inputs:
  foo: string
outputs:
  bar: string
steps:
  step1:
    scatter_method: blub
    in: []
    out: [out]
