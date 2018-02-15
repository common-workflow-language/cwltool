#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
inputs: []
requirements:
  StepInputExpressionRequirement: {}
outputs:
  out1:
    type: File
    outputSource: step1/out
  out2:
    type: File
    outputSource: step2/out
  out4:
    type: File
    outputSource: step4/out
steps:
  step1:
    in:
      r: {default: "1"}
    out: [out]
    run: echo.cwl
  step2:
    in:
      r:  {default: "2"}
    out: [out]
    run: echo.cwl
  step3:
    in:
      r:  {default: "5"}
    out: [out]
    run: echo.cwl
  step4:
    in:
      r:
        source: step3/out
        valueFrom: $(inputs.r.basename)
    out: [out]
    run: echo.cwl
