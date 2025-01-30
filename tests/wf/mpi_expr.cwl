#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

doc: |
  Trivial MPI test that prints the process IDs of each of the parallel
  processes. Requires Python (but you have cwltool running, right?)
  and an MPI implementation.

  This version takes the number of processes to use as an input and
  then passes this to the MPIRequirement using an expression.

baseCommand: python3
requirements:
  cwltool:MPIRequirement:
    processes: $(inputs.processes)
arguments: [-c, 'import os; print(os.getpid())']
inputs:
  processes:
    type: int

outputs:
  pids:
    type: stdout
