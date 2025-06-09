#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
doc: "This is a tool that can be launched without parameters"
baseCommand: [echo]
inputs:
  in:
    type: string
    default: "foo"
outputs:
  e_out:
    type: stdout
