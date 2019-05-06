#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1
id: stage_array_dirs
baseCommand:
  - ls
inputs:
  - id: input_list
    type: Directory[]
outputs:
  - id: output
    type: File[]
    outputBinding:
      glob:
      - testdir/a
      - rec/B
label: stage-array-dirs.cwl
requirements:
  - class: InitialWorkDirRequirement
    listing:
      - $(inputs.input_list)
