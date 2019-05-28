#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1
id: stage_array
arguments:
  - {shellQuote: false, valueFrom: "ls | grep -v lsout"}
inputs:
  - id: input_file
    type: File
  - id: optional_file
    type: File?
  - id: input_list
    type: 'File[]'
    secondaryFiles:
      - ^.tar
stdout: lsout
outputs:
  - id: output
    type: File?
    outputBinding:
      glob: lsout
label: stage-array.cwl
requirements:
  - class: InitialWorkDirRequirement
    listing:
      - $(inputs.input_file)
      - $(inputs.optional_file)
      - entry: $(inputs.input_list)
      - entryname: a
        entry: b
  - class: ShellCommandRequirement
