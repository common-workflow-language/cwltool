#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow

inputs: []
outputs: []

steps:
  task1:
    run: touch_tool.cwl
    in:
      message:
         default: one
    out: []
  task2:
    run: touch_tool.cwl
    in:
      message:
         default: two
    out: []
