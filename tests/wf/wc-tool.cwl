#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.0

hints:
  DockerRequirement:
   dockerPull: docker.io/debian:stable-slim

inputs:
  file1: File

outputs:
  output:
    type: File
    outputBinding: { glob: output }

baseCommand: [wc, -l]

stdin: $(inputs.file1.path)
stdout: output
