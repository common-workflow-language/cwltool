#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1
id: stage_file_array_basename
label: Stage File Array (with Directory Basename)
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
      - entry: "${ return {class: 'Directory', basename: 'input_dir', listing: inputs.input_list} }"
