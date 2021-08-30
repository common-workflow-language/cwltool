#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1
requirements:
  InlineJavascriptRequirement: {}
inputs:
  one:
    type: int
    inputBinding:
      position: $(self)
  two:
    type: int
    inputBinding:
      valueFrom: sensation!
      position: ${return "two";}
arguments:
  - position: ${return 2;}
    valueFrom: singular
outputs:
  out:
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
baseCommand: echo
stdout: out.txt
