#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
baseCommand: []
inputs:
  echo: boolean
outputs: []
arguments:
- position: 1
  shellQuote: false
  prefix: ''
  valueFrom: "non_existing_app"
- position: 0
  prefix: ''
  separate: false
  shellQuote: false
  valueFrom: "echo"
requirements:
- class: ShellCommandRequirement
