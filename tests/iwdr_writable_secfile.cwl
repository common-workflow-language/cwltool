cwlVersion: v1.2
class: CommandLineTool

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement: 
    listing:
      - entry: $(inputs.example_file_with_secondary)
        writable: true
inputs:
  example_file_with_secondary:
    type: File
    secondaryFiles:
    - pattern: "^.fastq"
      required: true
outputs: 
  same_file:
    type: stdout

baseCommand: cat
arguments: 
  - $(inputs.example_file_with_secondary.path)
  - $(inputs.example_file_with_secondary.path.split('.')[0]+'.fastq')
