#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
inputs:
  text:
    type: string
    inputBinding: {}
outputs: []
baseCommand: echo
