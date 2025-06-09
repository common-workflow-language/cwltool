#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  InitialWorkDirRequirement:
    listing:
      - entryname: env0.py
        entry: |
          import os
          for k, v in os.environ.items():
              print(f"{k}={v}", end="\0")

inputs: []
baseCommand: python3
arguments: ["env0.py"]
outputs:
  env:
    type: stdout
