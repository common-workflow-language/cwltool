#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool

hints:
  DockerRequirement:
    dockerPull: docker.io/alpine:latest

inputs: []

baseCommand: [ touch, file.ext1, file.ext2 ]

outputs:
  output:
    type: File
    secondaryFiles:
      - pattern: ^.ext2
        required: true
    outputBinding:
      glob: file.ext1
