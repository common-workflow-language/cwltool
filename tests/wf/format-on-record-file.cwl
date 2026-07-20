#!/usr/bin/env cwl-runner
# `format` on a record that contains a File field is valid.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  rec:
    type:
      type: record
      fields:
        - name: f
          type: File
    format: http://edamontology.org/format_1915
outputs: []
baseCommand: echo
