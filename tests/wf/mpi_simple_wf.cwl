#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: Workflow
doc: |
  Simple 2 step workflow to check that workflow steps are
  independently picking up on the number of processes.  First run the
  parallel get PIDs step (on the input num procs) then run (on a
  single proc) the line count. This should equal the input.
  
inputs:
  processes:
    type: int

steps:
  par_pids:
    run: mpi_expr.cwl
    in:
      processes: processes
    out:
      - pids

  count:
    run: mpi_line_count.cwl
    in:
      pid_file: par_pids/pids
    out:
      - line_count

outputs:
  line_count:
    type: File
    outputSource: count/line_count
    
