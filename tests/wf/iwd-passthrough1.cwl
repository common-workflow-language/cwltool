#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2
doc: |
  YAML |- syntax does not add trailing newline so in the listing entry
  below there is no whitespace surrounding the value
  $(inputs.filelist), so it is evaluated as a File object.  Compare to
  iwd-passthrough2.cwl

requirements:
  InitialWorkDirRequirement:
    listing:
      - entryname: "renamed-filelist.txt"
        entry: |-
          $(inputs.filelist)
inputs:
  filelist:
    type: File
outputs:
  filelist:
    type: File
    outputBinding:
      glob: renamed-filelist.txt
baseCommand: "true"
