#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

baseCommand: bash # python3

doc: "Extract PPI annotations from BioDL."
intent: [ http://edamontology.org/operation_0320 ]

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

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement: # the script takes a directory as input
    listing:
       - entry: |
           ${ return {"class": "Directory",
                      "listing": inputs.mmcif_files };
            }
         entryname: mmcif_directory
         # writable: true

inputs:
  script:
    type: File
    default:
      class: File
      location: ./ppi_annotations.py
  mmcif_files: # the download leaves us with an array of files, but script takes type Directory --> InitialWorkdirRequirement
    type: File[]
  train_dataset:
    type: File
    doc: "BioDL training set"
  test_dataset:
    type: File
    doc: "BioDL test set"
  output_directory_name:
    type: string
    default: "ppi_fasta"

arguments:
# - $(inputs.script.path)
# - "mmcif_directory"
# - $(inputs.train_dataset.path)
# - $(inputs.test_dataset.path)
# - "--outdir"
#- $(inputs.output_directory)
- -c
- |
  set -ex
  mkdir $(inputs.output_directory_name)
  touch $(inputs.output_directory_name)/$(inputs.train_dataset.nameroot)
  touch $(inputs.output_directory_name)/$(inputs.test_dataset.nameroot)


outputs:
  ppi_fasta_files:
    type: Directory
    outputBinding:
      glob: $(inputs.output_directory_name) 
