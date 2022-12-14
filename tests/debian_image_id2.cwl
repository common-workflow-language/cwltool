#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerImageId: 'docker.io_debian:stable-slim.sif'

inputs:
  message: string

outputs: []

baseCommand: echo
