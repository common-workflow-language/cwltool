#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool

hints:
  DockerRequirement:
    dockerPull: "https://hub.docker.com/_/alpine/"

inputs: []

baseCommand: [ "true" ]

outputs: []
