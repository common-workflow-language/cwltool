class: CommandLineTool
cwlVersion: v1.0
requirements:
  LoadListingRequirement:
    loadListing: null
inputs:
  d: Directory
outputs: []
arguments:
  [echo, "$(inputs.d.listing[0])"]
