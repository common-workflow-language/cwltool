cwlVersion: v1.0
class: CommandLineTool
requirements:
  - class: InlineJavascriptRequirement
baseCommand: ['echo']

inputs:
  - id: file
    type: Any
    inputBinding:
      valueFrom: "[$(self)]"

outputs: []

