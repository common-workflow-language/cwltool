#!/usr/bin/env cwl-runner
cwlVersion: cwl:draft-3
class: CommandLineTool
description: "Print the contents of a file to stdout using 'cat' running in a docker container."
hints:
  - class: DockerRequirement
    dockerPull: "debian:wheezy"
  - class: BlibberBlubberFakeRequirement
    fakeField: fraggleFroogle
inputs:
  - id: file1
    type: File
    label: "Input File"
    description: "The file that will be copied using 'cat'"
    inputBinding: {position: 1}
outputs:
  - id: output_file
    type: File
    outputBinding: {glob: output.txt}
baseCommand: cat
stdout: output.txt
