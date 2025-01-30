#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
baseCommand:
- touch
- 2.fastq
requirements:
- class: InitialWorkDirRequirement
  listing:
  - $(inputs.fasta_path)
inputs:
  fasta_path:
    type: File
    secondaryFiles: ^.fastq
outputs:
  fasta:
    type: File
    secondaryFiles: ^.fastq
    outputBinding:
      glob: $(inputs.fasta_path.basename)
