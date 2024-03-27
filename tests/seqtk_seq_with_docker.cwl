#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
id: "seqtk_seq"
doc: "Convert to FASTA (seqtk)"
inputs:
  - id: input1
    type: File
    inputBinding:
      position: 1
      prefix: "-a"
outputs:
  - id: output1
    type: File
    outputBinding:
      glob: out
baseCommand: ["seqtk", "seq"]
arguments: []
stdout: out
hints:
  SoftwareRequirement:
    packages:
    - package: seqtk
      version:
      - '1.4'
  DockerRequirement:
    dockerPull: quay.io/biocontainers/seqtk:1.4--he4a0461_1
