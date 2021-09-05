#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
inputs:
  sleep_time:
    type: int
    default: 3
    inputBinding: {}
outputs: []
requirements:
  InlineJavascriptRequirement: {}
  ToolTimeLimit:
    timelimit: '${return "42";}'
baseCommand: sleep
