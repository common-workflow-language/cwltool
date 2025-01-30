#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  a1: File
outputs: []
requirements:
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim
arguments: [cat, $(inputs.a1)]
