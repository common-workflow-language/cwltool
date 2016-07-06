$namespaces:
  edam: "http://edamontology.org/"
cwlVersion: cwl:draft-4.dev3
class: CommandLineTool
description: "Reverse each line using the `rev` command"
inputs:
  input:
    type: File
    inputBinding: {}
    format: edam:format_2330

outputs:
  output:
    type: File
    outputBinding:
      glob: output.txt
    format: edam:format_2330

baseCommand: rev
stdout: output.txt