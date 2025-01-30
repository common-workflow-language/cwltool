#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

doc: |
  Line count of input, but mpirun on a single process

baseCommand: wc
requirements:
  cwltool:MPIRequirement:
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
