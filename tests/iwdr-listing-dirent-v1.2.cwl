#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool
baseCommand: ["/bin/cat", "greet.txt"]
inputs: {}
requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing: '$( {"entry": "hello-dirent\n", "entryname": "greet.txt"} )'
outputs:
  out:
    type: stdout
stdout: output.txt