#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
id: "random_lines"
doc: "Select random lines from a file"
inputs:
  - id: seed
    type: int
    inputBinding:
      position: 1
      prefix: -s
  - id: input1
    type: File
    inputBinding:
      position: 2
  - id: num_lines
    type: int
    inputBinding:
      position: 3
outputs:
  output1:
    type: stdout
baseCommand: ["random-lines"]
arguments: []
hints:
  SoftwareRequirement:
    packages:
    - package: 'random-lines'
      version:
      - '1.0'
