#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0.dev4
description: "Print the contents of a file to stdout using 'cat' running in a docker container."
hints:
  DockerRequirement:
    dockerPull: debian:wheezy
inputs:
  file1:
    type: File
    label: Input File
    description: "The file that will be copied using 'cat'"
    inputBinding: {position: 1}
outputs:
  output_file:
    type: stdout
baseCommand: cat
stdout: cat-out
