class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: http://commonwl.org/cwltool#
requirements:
  cwltool:LoadListingRequirement:
    loadListing: null
inputs:
  d: Directory
outputs: []
arguments:
  [echo, "$(inputs.d.listing[0])"]
