#!/usr/bin/env cwl-runner

cwlVersion: v1.2.0-dev2
class: CommandLineTool
doc: |
  Trivial MPI test that prints the process IDs of each of the parallel
  processes. Requires Python (but you have cwltool running, right?)
  and an MPI implementation.

baseCommand: python
requirements:
  MPIRequirement:
    processes: 2
arguments: [-c, 'import os; print(os.getpid())']
inputs: []
outputs:
  pids:
    type: stdout
