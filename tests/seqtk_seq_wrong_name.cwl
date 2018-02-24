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
    - package: seqtk_seq
      version:
      - '1.2'
      specs:
      - https://anaconda.org/bioconda/seqtk
      - https://packages.debian.org/sid/seqtk
