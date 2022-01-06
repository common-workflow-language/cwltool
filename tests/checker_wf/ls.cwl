#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
inputs:
  intxt:
    type: File
    inputBinding: {}
outputs:
  lstxt:
    type: stdout
baseCommand: ls
stdout: ls.txt
