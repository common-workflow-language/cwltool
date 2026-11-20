cwlVersion: v1.0
class: CommandLineTool
requirements:
  InitialWorkDirRequirement:
    listing:
      - entryname: out.txt
        entry: |
          \$HOME $(inputs.msg)
inputs:
  msg: string
baseCommand: "true"
outputs:
  out:
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
