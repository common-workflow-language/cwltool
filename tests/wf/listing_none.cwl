#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: http://commonwl.org/cwltool#
requirements:
  cwltool:LoadListingRequirement:
    loadListing: no_listing
inputs:
  d: Directory
outputs: []
arguments:
  [echo, "$(inputs.d.listing[0])"]
