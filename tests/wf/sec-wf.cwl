class: Workflow
cwlVersion: v1.0
inputs:
  file1:
    type: File
outputs: []
steps:
  step1:
    in:
      file1: file1
    out: []
    run: sec-tool.cwl
