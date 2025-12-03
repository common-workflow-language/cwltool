#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerFile: |
      FROM docker.io/debian:stable-slim
    dockerImageId: customDebian

inputs:
  message: string

outputs: []

baseCommand: echo
arguments:
  - $(inputs.message)
