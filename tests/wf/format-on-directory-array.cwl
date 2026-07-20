#!/usr/bin/env cwl-runner
# `format` on Directory[] should warn: array items are not File.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  dirs:
    type: Directory[]
    format: http://edamontology.org/format_1915
    inputBinding: {}
outputs: []
baseCommand: echo
