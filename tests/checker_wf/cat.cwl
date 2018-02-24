#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
baseCommand: cat
inputs:
  cat_in:
    type: File[]
    inputBinding: {}
stdout: all.txt
outputs:
  txt:
    type: stdout
