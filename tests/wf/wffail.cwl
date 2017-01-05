class: Workflow
cwlVersion: v1.0
inputs: []
outputs:
  out1:
    type: File
    outputSource: step1/out
  out2:
    type: File
    outputSource: step2/out
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
