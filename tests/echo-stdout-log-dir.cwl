#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
id: echo
inputs:
  - id: inp
    type: string
    inputBinding: {}
outputs: []
baseCommand: echo
stdout: out.txt