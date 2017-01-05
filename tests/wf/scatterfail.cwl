class: Workflow
cwlVersion: v1.0
requirements:
  ScatterFeatureRequirement: {}
inputs:
  range:
    type: string[]
    default: ["1", "2", "3"]
outputs:
  out:
    type: File[]
    outputSource: step1/out
steps:
  step1:
    in:
      r: range
    scatter: r
    out: [out]
    run: echo.cwl
  step2:
    in:
      r: step1/out
    scatter: r
    out: []
    run: cat.cwl
