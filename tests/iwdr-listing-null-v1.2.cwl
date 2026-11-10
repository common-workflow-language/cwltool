#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool
baseCommand: ["/bin/echo", "null-ok"]
inputs: {}
requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing: '$(null)'
outputs:
  out:
    type: stdout
stdout: output.txt