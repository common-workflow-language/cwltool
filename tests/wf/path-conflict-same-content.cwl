#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow

inputs: {}

outputs:
  first_file:
    type: File
    outputSource: first/out
  second_file:
    type: File
    outputSource: second/out

steps:
  first:
    run: touch_tool.cwl
    in:
      message:
        default: 'foo.txt'
    out: [out]

  second:
    run: touch_tool.cwl
    in:
      message:
        default: 'foo.txt'
    out: [out]
