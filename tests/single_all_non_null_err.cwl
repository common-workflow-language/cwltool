cwlVersion: v1.2
class: Workflow

requirements:
  MultipleInputFeatureRequirement: {}
  InlineJavascriptRequirement: {}

inputs:
  inp:
    type: string?
    default: null

outputs:
  out:
    type: int[]
    outputSource:
    - root/out
    pickValue: all_non_null

steps:
  root:
    run:
      class: ExpressionTool
      inputs:
        strs: string
      outputs:
        out:
          type: int
      expression: |
        ${
          return {"out": inputs.strs.length}
        }
    in:
      strs:
        source:
        - inp
        pickValue: all_non_null
    out: [out]
