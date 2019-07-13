#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool

hints:
  DockerRequirement:
    dockerPull: debian:stretch-slim

inputs:
  name:
    type: string
    inputBinding:
      position: 0

outputs:
  empty_file:
    type: File
    outputBinding:
      glob: $(inputs.name)
      
baseCommand: [touch]
