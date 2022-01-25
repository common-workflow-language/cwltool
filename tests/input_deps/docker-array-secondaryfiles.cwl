#!/usr/bin/env cwl-runner

cwlVersion: v1.2

requirements:
  - class: DockerRequirement
    dockerPull: docker.io/debian:stable-slim
  - class: InlineJavascriptRequirement
  - class: ShellCommandRequirement

class: CommandLineTool

inputs:
  fasta_path:
    type:
      type: array
      items: File
    secondaryFiles:
      - pattern: .fai
        required: true
      - pattern: .crai
        required: false
      - .bai?
      - "${ if (inputs.require_dat) {return '.dat'} else {return null} }"
      - "${ return null; }"
      - pattern: .dat2
        required: $(inputs.require_dat)
  require_dat: boolean?

outputs:
  bai_list:
    type: File
    outputBinding:
      glob: "fai.list"
    secondaryFiles:
      - .bai?
      - pattern: "${ return null }"

arguments:
  - valueFrom: ${
        var fai_list = "";
        for (var i = 0; i < inputs.fasta_path.length; i ++) {
          fai_list += " cat " + inputs.fasta_path[i].path +".fai" + " >> fai.list && "
        }
        return fai_list.slice(0,-3)
        }
    position: 1
    shellQuote: false

baseCommand: []
