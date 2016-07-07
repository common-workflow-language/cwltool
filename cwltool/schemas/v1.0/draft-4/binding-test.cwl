#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.0.dev4

inputs:
  - id: reference
    type: File
    inputBinding: { position: 2 }

  - id: reads
    type:
      type: array
      items: File
      inputBinding: { prefix: "-YYY" }
    inputBinding: { position: 3, prefix: "-XXX" }

  - id: "#args.py"
    type: File
    default:
      class: File
      location: args.py
    inputBinding:
      position: -1

outputs: []

baseCommand: python
arguments: ["bwa", "mem"]
