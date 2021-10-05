#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerPull: docker.io/debian

inputs:
  message: string

outputs: []

baseCommand: echo
