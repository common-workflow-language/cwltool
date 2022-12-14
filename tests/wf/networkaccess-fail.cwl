#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
requirements:
  DockerRequirement:
    dockerPull: docker.io/python:3-slim
  NetworkAccess:
    networkAccess: true
inputs: []
outputs: []
baseCommand: python
arguments:
  - "-c"
  - valueFrom: |
      import urllib.request
      assert(urllib.request.urlopen("http://commonwl.org").code == 200)
