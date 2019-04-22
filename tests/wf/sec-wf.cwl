#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
inputs:
  file1:
    type: File
    secondaryFiles:
      - .idx

outputs: []
steps:
  step1:
    in:
      file1: file1
    out: []
    run: sec-tool.cwl
