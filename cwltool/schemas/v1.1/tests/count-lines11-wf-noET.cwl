#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.1

inputs:
  file1: File?

outputs:
  wc_output:
    type: File
    outputSource: step1/output

steps:
  step1:
    run: wc-tool.cwl
    in:
      file1:
        source: file1
        default:
          class: File
          location: whale.txt
    out: [output]
