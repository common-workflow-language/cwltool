#!/usr/bin/env cwl-runner

cwlVersion: v1.0

requirements:
  - class: DockerRequirement
    dockerPull: alpine:3.4
  - class: InitialWorkDirRequirement
    listing:
      - $(inputs.INPUT)
  - class: InlineJavascriptRequirement

class: CommandLineTool

inputs:
  - id: INPUT
    type: File

outputs:
  - id: OUTPUT
    type: File
    outputBinding:
      glob: $(inputs.INPUT.basename)
    secondaryFiles:
      - .fai

arguments:
  - valueFrom: $(inputs.INPUT.basename + ".fai")
    position: 0

baseCommand: [touch]
