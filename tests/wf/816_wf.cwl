class: Workflow
cwlVersion: v1.0
inputs:
  file:
    type: File
outputs: []
steps:
  - id: step
    in:
      file: file
    out: []
    run: 816_tool.cwl
