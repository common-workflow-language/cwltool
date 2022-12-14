#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerImageId: 'debian:stable-slim.img'

inputs:
  message: string

outputs: []

baseCommand: echo
