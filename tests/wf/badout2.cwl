#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
baseCommand: touch
arguments: [file1]
requirements:
  InlineJavascriptRequirement: {}
inputs: []
outputs:
  out:
    type: Directory
    outputBinding:
      outputEval: |
        $({"class": "Directory", "path": runtime.outdir+"/file1"})