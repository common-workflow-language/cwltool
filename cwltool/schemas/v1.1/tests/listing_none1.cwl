#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
requirements:
  InlineJavascriptRequirement: {}
inputs:
  d: Directory
outputs:
  out:
    type: boolean
    outputBinding:
      outputEval: $(inputs.d.listing === undefined)
baseCommand: "true"
