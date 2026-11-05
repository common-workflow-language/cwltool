#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
baseCommand: ["/bin/cat"]
inputs:
  infile:
    type: File
    inputBinding:
      position: 0
requirements:
  InitialWorkDirRequirement:
    listing: $(inputs.infile)
outputs:
  out:
    type: stdout
stdout: output.txt