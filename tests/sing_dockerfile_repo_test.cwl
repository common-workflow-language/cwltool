#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerFile: |
      FROM docker.io/debian:stable-slim
    dockerImageId: docker.io/nobody_who_exists/an_image:latest

inputs:
  message: string

outputs: []

baseCommand: echo
arguments:
  - $(inputs.message)
