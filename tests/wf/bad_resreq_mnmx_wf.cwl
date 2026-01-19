#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.2

requirements:
  ResourceRequirement:
    ramMin: 128
    ramMax: 64

inputs:
  message: string?

outputs: []

steps:
  hello_world:
    requirements:
      ResourceRequirement:
        ramMin: 64
        ramMax: 128
    run:
      class: CommandLineTool
      baseCommand: echo
      inputs:
        message:
          type: string?
          default: "Hello World"
      outputs: []
      arguments:
        - $(inputs.message)
    in:
      message: message
    out: []
