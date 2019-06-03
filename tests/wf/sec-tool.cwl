#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
inputs:
  file1:
    type: File
    secondaryFiles:
      - .idx
outputs: []
baseCommand: "true"
