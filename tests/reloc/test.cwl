cwlVersion: v1.2
class: CommandLineTool
inputs:
  inp: Directory
outputs:
  bar:
    type: File
    outputBinding:
      glob: dir2/foo
requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing:
      - $(inputs.inp)
arguments: [ls, -l]
