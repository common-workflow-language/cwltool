#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
hints:
  DockerRequirement:
   dockerPull: docker.io/debian:stable-slim
inputs:
  intxt:
    type: File
    inputBinding: {}
outputs:
  wctxt:
    type: stdout
baseCommand: wc
stdout: wc.txt
