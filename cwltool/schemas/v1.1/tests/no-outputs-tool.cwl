#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
doc: "CommandLineTool without outputs."
hints:
  DockerRequirement:
    dockerPull: debian:stretch-slim
inputs:
  file1:
    type: File
    label: Input File
    inputBinding: {position: 1}
outputs: []
baseCommand: echo
