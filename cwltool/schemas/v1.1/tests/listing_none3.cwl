#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
requirements:
  InlineJavascriptRequirement: {}
inputs:
  d:
    type: Directory
    loadListing: no_listing
outputs:
  out:
    type: boolean
    outputBinding:
      outputEval: $(inputs.d.listing === undefined)
baseCommand: "true"
