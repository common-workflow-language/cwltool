#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool
baseCommand: bash  # python3

label: Combine input features

doc: |
  "Combines the input features for each protein sequence into 1 file per sequence. Output is stored in a new directory."

hints:
  # DockerRequirement:
  #   dockerPull: amancevice/pandas:1.3.4-slim 
  SoftwareRequirement:
    packages:
      numpy:
        specs: [ https://anaconda.org/conda-forge/numpy ]
        version: [ "1.21.4" ]
      pandas:
        specs: [ https://anaconda.org/conda-forge/pandas ]
        version: [ "1.3.4" ]

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing: |
      ${
           return [{"entry": {"class": "Directory", "basename": "hhm_features_dir", "listing": inputs.hhm_features}, "writable": true}]
       }

arguments:
 # - $(inputs.script.path)
 # - $(inputs.input_sequences.path)
 # - "hhm_features_dir"
 # - $(inputs.pc7_features.path)
 # - $(inputs.psp19_features.path)
 # - "--outdir"
 # - ./$(inputs.outdir_name) # An output directory will be created in current working directory
 - -c
 - |
   set -ex
   mkdir $(inputs.outdir_name)
   touch $(inputs.outdir_name)/$(inputs.input_sequences.basename)


inputs:
  script:
    type: File
    default:
      class: File
      location: ./combine_inputs.py 
  input_sequences:
    type: Directory
    # default:
    #   class: Directory
    #   location: ../data/test_set/ppi_fasta # delete this later
  hhm_features:
    type: File[]
    # default:
    # - class: File
    #   location: ../final_test_run/2HKF_P.hhm
    # - class: File
    #   location: ../final_test_run/4W6W_A.hhm
    # - class: File
    #   location: ../final_test_run/4W6X_A.hhm
    # - class: File
    #   location: ../final_test_run/4W6Y_A.hhm
  pc7_features:
    type: Directory
    # default:
    #   class: Directory
    #   location: ../final_test_run/pc7_features
  psp19_features:
    type: Directory
    # default:
    #   class: Directory
    #   location: ../final_test_run/psp19_features
  outdir_name:
    type: string
    default: "input_features"

outputs:
  combined_features:
    type: Directory
    outputBinding:
      glob: $(inputs.outdir_name)

