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
    type: File
    outputBinding:
      outputEval: |
        $({"class": "File", "path": runtime.outdir+"/file2"})