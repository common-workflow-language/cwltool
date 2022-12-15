#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

requirements:
  InitialWorkDirRequirement:
    listing: $(inputs.pdb_archives)

baseCommand: bash # gunzip

arguments:
  - -c
  - |
    set -ex; for file in *.gz; do mv \${file} \${file%%.gz}; done

inputs:
  pdb_archives:
    type: File[]
    # inputBinding:
    #   position: 0

outputs: 
  cifs:
    type: File[]
    outputBinding:
      glob: "*.cif"
  pdbs:
    type: File[]
    outputBinding:
      glob: "*.pdb"

