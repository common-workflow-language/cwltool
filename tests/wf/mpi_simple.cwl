#!/usr/bin/env cwl-runner

cwlVersion: v1.2.0-dev2
class: CommandLineTool
label: trivial MPI test
baseCommand: python
requirements:
  MPIRequirement:
    processes: 2
arguments: [-c, 'import os; print(os.getpid())']
inputs: []
outputs:
  pids:
    type: stdout
