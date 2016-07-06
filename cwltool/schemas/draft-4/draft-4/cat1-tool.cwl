#!/usr/bin/env cwl-runner
cwlVersion: cwl:draft-4.dev3
class: CommandLineTool
description: "Print the contents of a file to stdout using 'cat' running in a docker container."
hints:
  DockerRequirement:
    dockerPull: debian:wheezy
  SoftwareRequirement:
    name: cat
inputs:
  file1:
    type: File
    inputBinding: {position: 1}
  numbering:
    type: boolean?
    inputBinding:
      position: 0
      prefix: -n
outputs: []
baseCommand: cat
