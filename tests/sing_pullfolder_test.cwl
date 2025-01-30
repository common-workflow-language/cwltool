#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim

inputs:
  message: string

outputs: []

baseCommand: echo
