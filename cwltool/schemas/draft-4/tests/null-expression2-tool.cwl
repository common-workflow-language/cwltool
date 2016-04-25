#!/usr/bin/env cwl-runner

class: ExpressionTool
requirements:
  - class: InlineJavascriptRequirement
cwlVersion: cwl:draft-4.dev1

inputs:
  - { id: i1, type: Any }

outputs:
  - { id: output, type: int }

expression: "$({'output': (inputs.i1 == 'the-default' ? 1 : 2)})"