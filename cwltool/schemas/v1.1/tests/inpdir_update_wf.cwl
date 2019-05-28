#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.1
inputs: []
requirements:
  InlineJavascriptRequirement: {}
outputs:
  a:
    type: File[]
    outputSource: step3/d1out
  b:
    type: File[]
    outputSource: step3/d2out
steps:
  step1:
    in:
      dirname: {default: step1dir}
    out: [out]
    run: mkdir.cwl
  step2:
    in:
      r: step1/out
    out: [out]
    run: updatedir_inplace.cwl
  step3:
    in:
      d1: step1/out
      d2: step2/out
    out: [d1out, d2out]
    run:
      class: ExpressionTool
      inputs:
        d1:
          type: Directory
          loadListing: shallow_listing
        d2:
          type: Directory
          loadListing: shallow_listing
      outputs:
        d1out: File[]
        d2out: File[]
      expression: "$({d1out: inputs.d1.listing, d2out: inputs.d2.listing})"
