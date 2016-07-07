class: CommandLineTool
cwlVersion: v1.0.dev4
requirements:
  - class: ShellCommandRequirement
inputs:
  inf: File
outputs:
  outlist:
    type: File
    outputBinding:
      glob: output.txt
baseCommand: []
arguments: ["cd", "$(inputs.inf.dirname)",
  {shellQuote: false, valueFrom: "&&"},
  "find", ".",
  {shellQuote: false, valueFrom: "|"},
  "sort"]
stdout: output.txt