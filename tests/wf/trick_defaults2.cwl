#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
inputs:
  inp1:
    type: File
    default:
      class: File
      location: hello.txt
      secondaryFiles:
        - class: Directory
          location: indir1
outputs: []
baseCommand: true
