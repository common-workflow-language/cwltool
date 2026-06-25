#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerImageId: 'docker.io_s_debian:stable-slim.img'

inputs:
  message: string

outputs: []

baseCommand: echo
