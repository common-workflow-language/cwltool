#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  DockerRequirement:
    dockerPull: docker.io/python:3-slim
  cwltool:WorkReuse:
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
