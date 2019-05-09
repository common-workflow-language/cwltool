#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerPull: debian

inputs:
  message: string

outputs: []

baseCommand: echo
