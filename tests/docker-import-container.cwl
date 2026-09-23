#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool

hints:
  DockerRequirement:
    dockerImport: "nonexistent.tar.gz"

inputs: []

baseCommand: [ "true" ]

outputs: []
