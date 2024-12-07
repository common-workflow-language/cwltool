#!/usr/bin/env cwl-runner
cwlVersion: v1.3.0-dev1
class: Workflow
requirements:
  InlineJavascriptRequirement: {}
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
inputs:
  i1: int
  i2: int
outputs:
  o1:
    type: int
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
    when: |
      ${
      if (inputs.i1 != 1) {
      throw new Error("failed");
      } else {
      return true;
      }
      }
    loop:
      i1: o1
    outputMethod: last_iteration
    in:
      i1: i1
      i2: i2
    out: [o1]
