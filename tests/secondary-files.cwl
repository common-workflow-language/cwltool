#!/usr/bin/env cwl-runner

cwlVersion: v1.1

requirements:
  - class: InlineJavascriptRequirement
  - class: ShellCommandRequirement

class: CommandLineTool

inputs:
  fasta_path:
    type: File
    secondaryFiles:
      - pattern: ^.fastq
        required: true
      - pattern: .crai
        required: false
      - .bai?
      - pattern: "${ return null }"

outputs:
  bai_list:
    type: File
    outputBinding:
      glob: lsout
    secondaryFiles:
      - .bai?
      - pattern: "${ return null }"
      - pattern: .crai
        required: false
      - pattern: .idx

baseCommand: ["ls"]

stdout: lsout
