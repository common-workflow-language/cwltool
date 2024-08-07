#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: CommandLineTool 
# hints:
#   DockerRequirement:
#     dockerPull: amancevice/pandas:1.3.4-slim # Script needs numpy which is a dependency of pandas
#   SoftwareRequirement:
#     packages: 
#       numpy:
#         specs: [ https://anaconda.org/conda-forge/numpy ]

baseCommand: bash  # python3

doc: PC7 features are assigned to each residue in each protein sequence. Output is a directory of files (1 per sequence).
# intent: [ http://edamontology.org/operation_0361 ]

inputs:
  script:
    type: File
    default: 
      class: File
      location: ./get_pc7_inputs.py 
    # inputBinding: { position: 1 }
  fasta:
    type: Directory 
    format: edam:format_2200 # fasta-like (text)
    # inputBinding:
    #   position: 2
  outdir:
    type: string
    # inputBinding: 
    #   position: 3
    #   prefix: -o
    default: "pc7_features"

arguments:
 - -c
 - |
   mkdir $(inputs.outdir)
   touch $(inputs.outdir)/$(inputs.fasta.nameroot)

outputs: 
  pc7_features: 
    type: Directory 
    outputBinding:
      glob: $(inputs.outdir)

s:mainEntity: # add that this is a commandlinetool
  s:programmingLanguage: Python
  s:codeRepository: https://github.com/RenskeW/cwl-epitope/blob/b5e31d42006fd7003716f57963646d47d1154549/tools/get_pc7_inputs.py
  s:isBasedOn:
  - s:additionalType: s:SoftwareApplication
    s:name: OPUS-TASS
    s:identifier: https://bio.tools/opus-tass

$namespaces:
  s: https://schema.org/
  edam: http://edamontology.org/

$schemas:
- https://schema.org/version/latest/schemaorg-current-https.rdf
- https://edamontology.org/EDAM_1.25.owl
