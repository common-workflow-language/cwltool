#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1
id: stage_file_array
label: Stage File Array
arguments: [ls]
inputs:
  - id: input_list
    type: 'File[]'
    secondaryFiles:
      - .sec
outputs:
  - id: output
    type: File[]
    outputBinding:
      glob: input_dir/*
requirements:
  - class: InlineJavascriptRequirement
  - class: InitialWorkDirRequirement
    listing:
      - entryname: input_dir
        entry: "${ return {class: 'Directory', listing: inputs.input_list} }"
