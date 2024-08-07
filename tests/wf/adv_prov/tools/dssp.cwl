#!/usr/bin/env cwl-runner

cwlVersion: v1.2 
class: CommandLineTool
baseCommand: bash  # python3

doc: "Use DSSP to extract secondary structure and solvent accessibility from PDB files."
intent: [ http://edamontology.org/operation_0320 ]

requirements:
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement: # the script takes a directory as input
    listing: |
      ${
           return [{"entry": {"class": "Directory", "basename": "pdb_source_dir", "listing": inputs.pdb_files}, "writable": true}]
       }

hints:
  # DockerRequirement:
  #   dockerPull: biopython/biopython@sha256:437075df44b0c9b3da96f71040baef0086789de7edf73c81de4ace30a127a245
  SoftwareRequirement:
    packages:
      pandas:
        version: [ "0.19.1" ]
        specs: [ https://pypi.org/project/pandas/ ]
      biopython:
        specs: [ https://pypi.org/project/biopython/ ]
        version: [ "1.75" ]
      dssp:
        specs: [ https://swift.cmbi.umcn.nl/gv/dssp/ ]
        version: [ "2.0.4" ] # this version does not support mmCIF files
      python:
        version: [ "3.5" ]

arguments:
 # - $(inputs.script.path)
 # - "pdb_source_dir"
 # - "-o"
 # - $(inputs.output_dir)
 # - "-d"
 # - $(inputs.dssp)
 # - "-c"
 # - $(inputs.rsa_cutoff)
 - -c
 - |
   set -ex
   mkdir $(inputs.output_dir)
   touch $(inputs.output_dir)/$(inputs.pdb_files[0].nameroot)


inputs:
  script:
    type: File
    default: 
      class: File
      location: ./dssp_RASA.py 
  pdb_files:
    type: File[]
    doc: "Protein structures in PDB format."
  output_dir:
    type: string
    default: "dssp_output"
  dssp:
    type: string
    default: "dssp" # for newer dssp versions: mkdssp
  rsa_cutoff:
    type: float
    default: 0.06
    doc: "Threshold exposed surface area for considering amino acids buried."

outputs:
  dssp_output_files:
    type: Directory
    outputBinding:
      glob: $(inputs.output_dir)

s:author:
- class: s:Person
  s:name: "Renske de Wit"
s:license: https://spdx.org/licenses/Apache-2.0
s:dateCreated: "2022-05-28"
s:mainEntity:
  class: s:SoftwareApplication
  s:license: https://spdx.org/licenses/Apache-2.0
  s:author:
  - class: s:Person
    s:name: "DS"
  s:description: "Script which takes a directory of pdb files as input and calculates relative surface accessibility for each residue in the protein sequence."
  s:basedOn:
  - class: s:SoftwareApplication
    s:name: "DSSP"
  
$namespaces:
  s: https://schema.org/
  edam: http://edamontology.org/

$schemas:
- https://schema.org/version/latest/schemaorg-current-https.rdf
- https://edamontology.org/EDAM_1.25.owl



