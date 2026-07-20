#!/usr/bin/env cwl-runner
# `format` on File[] is valid (items is a string after load, not a list).
cwlVersion: v1.2
class: CommandLineTool
inputs:
  files:
    type: File[]
    format: http://edamontology.org/format_1915
    inputBinding: {}
outputs: []
baseCommand: echo
