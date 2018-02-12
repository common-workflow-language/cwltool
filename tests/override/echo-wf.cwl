#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
inputs:
  m1: string
outputs:
  out:
    type: string
    outputSource: step1/out
steps:
  step1:
    in:
      m1: m1
    out: [out]
    run: echo.cwl
