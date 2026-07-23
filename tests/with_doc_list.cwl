#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool
inputs:
  - id: message
    type: string
    doc:
      - "The message to print."
      - "Second line for the message input."
    inputBinding: {}
baseCommand: echo
outputs: []

doc:
  - "This should be shown in help message, line one."
  - "This should be shown in help message, line two."
