#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:TimeLimit:
    timelimit: 3
inputs: []
outputs: []
baseCommand: [sleep, "5"]
