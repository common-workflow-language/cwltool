#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
requirements:
  ShellCommandRequirement: {}
hints:
  EnvVarRequirement:
    envDef:
      MESSAGE: hello1
inputs:
  m1: string
outputs:
  - id: out
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
arguments: ["echo", $(inputs.m1), {shellQuote: false, valueFrom: "$MESSAGE"}]
stdout: out.txt
