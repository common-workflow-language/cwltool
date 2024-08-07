#!/usr/bin/env cwl-runner

cwlVersion: v1.2 
class: CommandLineTool

baseCommand: bash  # python3

intent: [ http://edamontology.org/operation_0320 ]

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement: # the script takes a directory as input
    listing: |
      ${
           return [{"entry": {"class": "Directory", "basename": "mmcif_directory", "listing": inputs.mmcif_files}, "writable": true}]
       }

doc: |
  Runs Python script which takes directory of mmCIF files as input and outputs directory of FASTA files with protein sequence + epitope annotations.

hints:
  # DockerRequirement:
  #   dockerImageId: pdbecif-pandas:20220620
  #   dockerFile: |                                                               
  #     FROM docker.io/debian:stable-slim                                                                                                                         
  #     RUN apt-get update && apt-get install -y --no-install-recommends python3-pip
  #     RUN python3 -m pip install PDBeCif pandas  
  SoftwareRequirement:
    packages:
      pandas:
        specs: [ https://anaconda.org/conda-forge/pandas ]
        version: [ "1.2.4" ]
      python:
        version: [ "3.9.1" ]
      pdbecif:
        specs: [ https://pypi.org/project/PDBeCif/ ]
        version: [ "1.5" ]

arguments:
 # - $(inputs.script.path)
 # - "mmcif_directory"
 # - $(inputs.sabdab_processed.path)
 # - "--fasta_directory"
 # - $(inputs.fasta_output_dir)
 # - "--df_directory"
 # - $(inputs.df_output_dir)
 - -c
 - |
   mkdir $(inputs.fasta_output_dir) $(inputs.df_output_dir);
   touch $(inputs.fasta_output_dir)/$(inputs.mmcif_files[0].basename).fasta 
   touch $(inputs.df_output_dir)/$(inputs.mmcif_files[0].basename).df

inputs:
  script:
    type: File
    default:
      class: File
      location: ./epitope_annotation_pipeline.py
  mmcif_files:
    type: File[]
    doc: mmCIF file array
  sabdab_processed:
    format: iana:text/csv 
    type: File
    doc: "table of PDB entries with associated H, L and antigen chain."
  fasta_output_dir:
    type: string
    default: "./epitope_fasta"
  df_output_dir:
    type: string
    default: "./epitope_df"

outputs:
  epitope_fasta_dir:
    type: Directory
    outputBinding:
      glob: $(inputs.fasta_output_dir)
  epitope_df_dir:
    type: Directory
    outputBinding:
      glob: $(inputs.df_output_dir)

s:dateCreated: 2022-05-30

s:mainEntity:
  s:additionalType: s:SoftwareApplication
  s:author:
  - s:name: "Katharina Waury"
  s:dateCreated: 2022-02-10
  s:programmingLanguage: Python
  s:description: "Script which extracts epitope annotations and dataframes from mmCIF files."

$namespaces:
  s: https://schema.org/
  edam: http://edamontology.org/
  iana: https://www.iana.org/assignments/media-types/

$schemas:
- https://schema.org/version/latest/schemaorg-current-https.rdf
- https://edamontology.org/EDAM_1.25.owl
