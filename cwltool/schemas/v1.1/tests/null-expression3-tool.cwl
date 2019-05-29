#!/usr/bin/env cwl-runner

class: ExpressionTool
requirements: { InlineJavascriptRequirement: {} }
cwlVersion: v1.1

inputs: []

outputs:
  output: Any

expression: "$({'output': null })"
