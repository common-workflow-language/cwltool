#!/usr/bin/env cwl-runner
$namespaces:
  edam: "http://edamontology.org/"
cwlVersion: v1.0
class: CommandLineTool
requirements:
  InlineJavascriptRequirement: {}
doc: "Reverse each line using the `rev` command"
inputs:
  input:
    type: File
    inputBinding: {}
    format:
      - |
        ${ return ["http://edamontology.org/format_2330", 42];}

outputs:
  output:
    type: File
    outputBinding:
      glob: output.txt
    format: |
      ${return "http://edamontology.org/format_2330";}

baseCommand: rev
stdout: output.txt
