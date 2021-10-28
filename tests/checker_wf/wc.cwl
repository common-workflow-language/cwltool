#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
inputs:
  intxt:
    type: File
    inputBinding: {}
outputs:
  wctxt:
    type: stdout
baseCommand: wc
stdout: wc.txt
