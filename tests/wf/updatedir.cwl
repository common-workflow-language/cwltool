#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
requirements:
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.r)
        entryname: inp
        writable: true
inputs:
  r: Directory
outputs:
  out:
    type: Directory
    outputBinding:
      glob: inp
arguments: [touch, inp/blurb]