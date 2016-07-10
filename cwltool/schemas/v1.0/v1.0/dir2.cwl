class: CommandLineTool
cwlVersion: v1.0
hints:
  DockerRequirement:
    dockerPull: debian:8
  ShellCommandRequirement: {}
inputs:
  indir: Directory
outputs:
  outlist:
    type: File
    outputBinding:
      glob: output.txt
baseCommand: []
arguments: ["cd", "$(inputs.indir.path)",
  {shellQuote: false, valueFrom: "&&"},
  "find", ".",
  {shellQuote: false, valueFrom: "|"},
  "sort"]
stdout: output.txt