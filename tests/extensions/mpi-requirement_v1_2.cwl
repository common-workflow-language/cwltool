#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2
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