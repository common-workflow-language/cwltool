#!/usr/bin/env cwl-runner
$namespaces:
  edam: "http://edamontology.org/"
$schemas:
  - empty.ttl
cwlVersion: v1.0
class: CommandLineTool
doc: "Reverse each line using the `rev` command"
inputs:
  input:
    type: File
    inputBinding: {}
    format: edam:format_2330

outputs:
  output:
    type: File
    outputBinding:
      glob: output.txt
    format: edam:format_2330

baseCommand: rev
stdout: output.txt
