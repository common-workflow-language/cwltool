#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: ExpressionTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  InlineJavascriptRequirement: {}
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
expression: >
  ${return {'o1': inputs.i1 + inputs.i2};}
