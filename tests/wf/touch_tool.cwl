#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: CommandLineTool
baseCommand: touch
requirements:
  DockerRequirement:
    dockerPull: alpine
inputs:
  message:
    type: string
    inputBinding:
      position: 1
outputs:
  - id: out
    type: File
    outputBinding:
      glob: "*"
