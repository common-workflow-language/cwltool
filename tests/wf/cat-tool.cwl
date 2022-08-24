#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.0

hints:
  DockerRequirement:
    dockerPull: docker.io/bash:4.4`

inputs:
  file1: File

outputs:
  output:
    type: File
    outputBinding: { glob: output }

baseCommand: [cat]

stdin: $(inputs.file1.path)
stdout: output
