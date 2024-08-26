#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

baseCommand: bash  # python3

# hints:
#   DockerRequirement:
#     dockerPull: amancevice/pandas:1.3.4-slim
#   SoftwareRequirement:
#     packages:
#       pandas:
#         specs: [ https://anaconda.org/conda-forge/pandas ]
#         version: [ "1.3.4" ]
#       python:
#         version: [ "3.9.7" ]

arguments:
 # - $(inputs.script.path)
 # - $(inputs.epitope_directory.path)
 # - $(inputs.ppi_directory.path)
 # - $(inputs.dssp_directory.path)
 # - "--outdir"
 # - $(inputs.output_directory)
 - -c
 - |
   set -ex
   mkdir $(inputs.output_directory)
   touch $(inputs.output_directory)/$(inputs.epitope_directory.basename)
   touch $(inputs.output_directory)/$(inputs.ppi_directory.basename)
   touch $(inputs.output_directory)/$(inputs.dssp_directory.basename)


inputs:
  script:
    type: File
    default:
      class: File
      location: ./combine_labels.py
  epitope_directory:
    type: Directory
    doc: Directory with FASTA files with epitope annotations.
  ppi_directory:
    type: Directory
    doc: Directory with FASTA files with PPI annotations.
  dssp_directory:
    type: Directory
    doc: Directory with DSSP output files.
  output_directory:
    type: string
    default: "./combined_labels"

outputs:
  labels_combined:
    type: Directory
    doc: "Directory with 1 file per sequence, containing label values for each residue"
    outputBinding:
      glob: $(inputs.output_directory)




