#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
inputs:
  inp1:
    type: File
    default:
      class: File
      location: indir1/hello.txt
  inp2:
    type: Directory
    default:
      class: Directory
      location: indir1
outputs: []
baseCommand: true
