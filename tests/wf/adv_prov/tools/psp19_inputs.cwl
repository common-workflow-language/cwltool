#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool 
# hints:
#   DockerRequirement:
#     dockerPull: amancevice/pandas:1.3.4-slim
#   SoftwareRequirement:
#     packages: 
#       numpy:
#         specs: [ https://anaconda.org/conda-forge/numpy ]
      # python:
      #   version:

baseCommand: bash  # python3

inputs:
  script:
    type: File
    default: 
      class: File
      location: ./get_psp19_inputs.py  
    # inputBinding: 
    #   position: 1
  fasta:
    type: Directory
    format: edam:format_2200
    # inputBinding:
    #   position: 2
  outdir:
    type: string
    # inputBinding: 
    #   position: 3
    #   prefix: -o
    default: "psp19_features"

arguments:
 - -c
 - |
   set -ex
   mkdir $(inputs.outdir)
   touch $(inputs.outdir)/$(inputs.fasta.nameroot)

outputs: 
  psp19_features: 
    type: Directory 
    outputBinding:
      glob: $(inputs.outdir)

$namespaces:
  edam: http://edamontology.org/

$schemas:
- https://edamontology.org/EDAM_1.25.owl
