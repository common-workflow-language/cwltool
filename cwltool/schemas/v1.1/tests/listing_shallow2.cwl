#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
requirements:
  InlineJavascriptRequirement: {}
inputs:
  d:
    type: Directory
    loadListing: shallow_listing
outputs:
  out:
    type: boolean
    outputBinding:
      outputEval: '$(inputs.d.listing.length === 1 && inputs.d.listing[0].listing === undefined)'
baseCommand: "true"
