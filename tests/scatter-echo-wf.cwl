#!/usr/bin/env cwl-runner
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
cwlVersion: v1.1
class: Workflow
requirements:
  ScatterFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}

inputs:
  texts:
    type: string[]

outputs: []

steps:
  echo:
    run: echo_no_output.cwl
    scatter: text
    hints:
      cwltool:StepNameHint:
        stepname: $("test_" + inputs.text.split('.')[0])
    in:
      text: texts
    out: []
