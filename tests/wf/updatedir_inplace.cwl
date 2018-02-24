#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: http://commonwl.org/cwltool#
requirements:
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.r)
        entryname: inp
        writable: true
  cwltool:InplaceUpdateRequirement:
    inplaceUpdate: true
inputs:
  r: Directory
outputs:
  out:
    type: Directory
    outputBinding:
      glob: inp
arguments: [touch, inp/blurb]