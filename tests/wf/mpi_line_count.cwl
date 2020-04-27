#!/usr/bin/env cwl-runner

cwlVersion: v1.2.0-dev2
class: CommandLineTool
doc: |
  Line count of input, but mpirun on a single process

baseCommand: wc
requirements:
  MPIRequirement:
    processes: 1

arguments: [-l]
stdin: $(inputs.pid_file.path)
stdout: line_count
inputs:
  pid_file:
    type: File

outputs:
  line_count:
    type: stdout
