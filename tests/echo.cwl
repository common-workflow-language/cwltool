cwlVersion: cwl:draft-4.dev3
class: CommandLineTool
inputs:
  - id: inp
    type: string
    inputBinding: {}
outputs:
  - id: out
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
baseCommand: echo
stdout: out.txt