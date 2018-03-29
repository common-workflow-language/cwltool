#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
requirements:
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
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
    run:
      class: Workflow
      id: subtool
      inputs:
        r: string
      outputs:
        out:
          type: File
          outputSource: sstep1/out
      steps:
        sstep1:
          in:
            r: r
          out: [out]
          run: echo.cwl
        sstep2:
          in:
            r: sstep1/out
          out: []
          run: cat.cwl
