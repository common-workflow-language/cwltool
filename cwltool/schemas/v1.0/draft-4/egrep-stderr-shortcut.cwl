#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0.dev4
description: "Test of capturing stderr output in a docker container."
hints:
  DockerRequirement:
    dockerPull: debian:wheezy

inputs: []

outputs:
  output_file:
    type: stderr

baseCommand: egrep
successCodes: [2]
