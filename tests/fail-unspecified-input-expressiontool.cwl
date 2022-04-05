cwlVersion: v1.0
class: ExpressionTool

requirements:
  InlineJavascriptRequirement: {} 

inputs:
  in:
    type: string

outputs:
  out:
    type: string

expression: |
  ${ 
    return {"out": inputs.in +" "+inputs.in2};
  }
