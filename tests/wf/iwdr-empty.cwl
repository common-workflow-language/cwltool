#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.0
baseCommand: ["cat", "empty_file"]

requirements:
  InitialWorkDirRequirement:
    listing:
      - entryname: empty_file
        entry: ""

inputs: []
outputs: []