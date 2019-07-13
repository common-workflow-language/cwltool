#!/usr/bin/env cwl-runner

class: CommandLineTool
cwlVersion: v1.1

requirements:
  - class: DockerRequirement
    dockerPull: debian:stretch-slim

inputs:
  file1: stdin

outputs:
  output:
    type: File
    outputBinding: { glob: output }

baseCommand: [wc]

stdout: output
