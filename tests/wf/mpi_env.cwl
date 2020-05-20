#!/usr/bin/env cwl-runner

cwlVersion: v1.2.0-dev2
class: CommandLineTool

baseCommand: env
requirements:
  MPIRequirement:
    processes: 1
inputs: {}
outputs:
  environment:
    type: stdout
