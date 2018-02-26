#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.0
baseCommand: ["cat", "example.conf"]

requirements:
  InitialWorkDirRequirement:
    listing:
      - entryname: example.conf
        entry: |
          CONFIGVAR=$(inputs.message)

inputs:
  message: string
outputs:
  out:
    type: string
    outputBinding:
      glob: example.conf
      loadContents: true
      outputEval: $(self[0].contents)