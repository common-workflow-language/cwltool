#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerImageId: container_repo/alpine

inputs:
  message: string

outputs: []

baseCommand: echo
