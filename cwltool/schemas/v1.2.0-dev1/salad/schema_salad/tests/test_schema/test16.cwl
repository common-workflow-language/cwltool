#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo
inputs:
  message:
    type: string
    inputBinding:
      position: 1
      posi
outputs:
  hello_output:
    type: File
    outputBinding:
      glob: hello-out.txt
stdout: hello-out.txt
