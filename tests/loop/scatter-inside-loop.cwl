#!/usr/bin/env cwl-runner
cwlVersion: v1.3.0-dev1
class: Workflow
requirements:
  InlineJavascriptRequirement: {}
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
inputs:
  i1: int[]
  i2: int
outputs:
  o1:
    type: int[]
    outputSource: scatter/o1
steps:
  scatter:
    run:
      class: Workflow
      inputs:
        i1: int[]
        i2: int
      outputs:
        o1:
          type: int[]
          outputSource: subworkflow/o1
      steps:
        subworkflow:
          run:
            class: ExpressionTool
            inputs:
              i1: int
              i2: int
            outputs:
              o1: int
            expression: >
              ${return {'o1': inputs.i1 + inputs.i2};}
          in:
            i1: i1
            i2: i2
          out: [o1]
          scatter: i1
    in:
      i1: i1
      i2: i2
    out: [o1]
    when: $(inputs.i1[0] < 10)
    loop:
      i1: o1
    outputMethod: last_iteration
