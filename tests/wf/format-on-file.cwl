#!/usr/bin/env cwl-runner
# Companion fixture: `format` on a File input is valid and must NOT warn.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  inf:
    type: File
    format: http://edamontology.org/format_1915
    inputBinding: {}
outputs: []
baseCommand: echo
