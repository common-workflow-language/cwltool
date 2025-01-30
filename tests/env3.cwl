#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs: []
baseCommand: env
arguments: ["-0"]
outputs:
  env:
    type: stdout
