#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2

requirements:
  ResourceRequirement:
      coresMin: 4
      coresMax: 2

inputs: []
outputs: []

baseCommand: ["echo", "Hello World"]

