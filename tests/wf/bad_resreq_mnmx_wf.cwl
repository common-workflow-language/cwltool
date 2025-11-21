#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.2

requirements:
  ResourceRequirement:
      ramMin: 128
      ramMax: 64

inputs: []
outputs: []

steps:
  hello_world:
    requirements:
      ResourceRequirement:
        ramMin: 64
        ramMax: 128
    run:
        class: CommandLineTool
        baseCommand: [ "echo", "Hello World" ]
        inputs: [ ]
        outputs: [ ]
    out: [ ]
    in: [ ]
