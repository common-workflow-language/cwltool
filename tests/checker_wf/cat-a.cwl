#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
inputs:
  intxt:
    type: File[]
    inputBinding: {}
outputs:
  cattxt:
    type: stdout
baseCommand: [cat, -A]
stdout: cat.txt
