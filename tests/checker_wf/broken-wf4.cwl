#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
inputs:
  letters0:
    type: string
    default: "a0"

outputs:
  all:
    type: File
    outputSource: echo_w

steps:
  echo_w:
    run: echo.cwl
    in:
      echo_in: letters0
    out: [txt]

