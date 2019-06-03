#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerImageId: 'debian.img'

inputs:
  message: string

outputs: []

baseCommand: echo