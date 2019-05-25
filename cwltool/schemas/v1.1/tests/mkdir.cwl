#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
inputs:
  dirname: string
outputs:
  out:
    type: Directory
    outputBinding:
      glob: $(inputs.dirname)
arguments: [mkdir, $(inputs.dirname)]
