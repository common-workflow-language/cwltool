#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow

requirements:
 InlineJavascriptRequirement: {}

inputs: []

steps:
  step1:
    in: {}
    when: $(self !== null)
    run:
      class: ExpressionTool
      inputs: []
      requirements:
        InlineJavascriptRequirement: {}
      expression: |
        $({"result": "huzzah!"})
      outputs:
        result: string
    out: [ result ]

outputs:
  required:
    type: string
    outputSource: step1/result
