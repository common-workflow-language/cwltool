#!/usr/bin/env cwl-runner

class: ExpressionTool
requirements:
  - class: InlineJavascriptRequirement
cwlVersion: cwl:draft-4.dev3

inputs:
  i1: Any

outputs:
  output: int

expression: "$({'output': (inputs.i1 == 'the-default' ? 1 : 2)})"