#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
doc: "Create a file under /tmp, symlink it to working directory and glob symlink. The executor should NOT resolve this symlink"
hints:
  DockerRequirement:
    dockerPull: alpine
inputs: []
outputs:
  output_file:
    type: File
    outputBinding: {glob: symlink.txt}

requirements:
  - class: ShellCommandRequirement

arguments:
  - echo
  - "Who's gonna drive you home"
  - {valueFrom: "> /tmp/original.txt", shellQuote: false}
  - {valueFrom: " && ", shellQuote: false}
  - ln
  - -s
  - /tmp/original.txt
  - symlink.txt