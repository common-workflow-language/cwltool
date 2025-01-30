#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: Workflow

inputs:
  range:
    type: int
outputs:
  output:
    type: File[]
    outputSource:
      generate_files/output

steps:
  generate_list:
    requirements:
      - class: InlineJavascriptRequirement
    run:
      class: ExpressionTool
      inputs:
        max: 
          type: int
          default: 100
      outputs:
        numbers:
          type: int[]
      expression: |
        ${
          var numberList = Array.apply(null, Array(inputs.max)).map(function(_, i) { return i});
          return { "numbers": numberList } 
         }
    in:
      max: range
    out:
      - numbers
  generate_files:
    requirements:
      - class: ScatterFeatureRequirement
    scatter: number
    run:
      class: CommandLineTool
      inputs:
        number:
          type: int
          inputBinding:
            position: 10
      baseCommand: [ echo ]
      stdout: output.txt
      outputs:
        output:
          type: stdout
    in:
      number: generate_list/numbers
    out:
      - output
