class: CommandLineTool
cwlVersion: v1.0
requirements:
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.r)
        writable: true
inputs:
  r: File
outputs:
  out:
    type: File
    outputBinding:
      outputEval: $(inputs.r)
arguments: [cat, $(inputs.r.basename)]