#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  InlineJavascriptRequirement: {}
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
  cwltool:Loop:
    loopWhen: $(inputs.i1 < 10)
    loop:
      i1: o1
    outputMethod: last
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
    in:
      i1: i1
      i2: i2
    when: $(inputs.i2 < 10)
    out: [o1]
