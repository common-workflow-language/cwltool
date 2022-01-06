#!/usr/bin/env cwl-runner

cwlVersion: v1.1
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

baseCommand: env
requirements:
  cwltool:MPIRequirement:
    processes: 1
inputs: {}
outputs:
  environment:
    type: stdout
