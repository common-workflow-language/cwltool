#!/usr/bin/env cwl-runner
# `format` on a record with no File field should warn.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  rec:
    type:
      type: record
      fields:
        - name: s
          type: string
    format: http://edamontology.org/format_1915
outputs: []
baseCommand: echo
