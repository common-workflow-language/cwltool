#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
requirements:
  DockerRequirement:
    dockerPull: python:3
  WorkReuse:
    enableReuse: false
inputs: []
outputs:
  page: stdout
stdout: time.txt
baseCommand: python
arguments:
  - "-c"
  - valueFrom: |
      import time
      print(time.time())
