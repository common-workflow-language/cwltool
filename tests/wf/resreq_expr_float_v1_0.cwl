cwlVersion: v1.0
class: CommandLineTool
requirements:
  - class: InlineJavascriptRequirement
  - class: ResourceRequirement
    tmpdirMin: $((2 * inputs.input_bam.size) / 3.14159)
    outdirMin: $((2 * inputs.input_bam.size) / 3.14159)

inputs:
  input_bam: File

arguments:
 - |
   {"result": $(runtime) }

stdout: cwl.output.json

outputs:
  result: Any

baseCommand: [echo]
