class: CommandLineTool
cwlVersion: v1.0
requirements:
  LoadListingRequirement:
    loadListing: shallow
inputs:
  d: Directory
outputs: []
arguments:
  [echo, "$(inputs.d.listing[0].listing[0])"]
