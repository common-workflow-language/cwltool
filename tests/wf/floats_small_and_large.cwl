cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo
requirements:
  InlineJavascriptRequirement: {}

inputs:
 annotation_prokka_evalue:
   type: float
   default: 0.00001
   inputBinding: {}

 annotation_prokka_evalue2:
   type: float
   default: 1.23e-05
   inputBinding: {}

 annotation_prokka_evalue3:
   type: float
   default: 1.23e5
   inputBinding: {}

 annotation_prokka_evalue4:
   type: float
   default: 1230000
   inputBinding: {}


arguments: [ -n ]

stdout: dump

outputs:
  result:
    type: string
    outputBinding:
      glob: dump
      loadContents: true
      outputEval: $(self[0].contents)
