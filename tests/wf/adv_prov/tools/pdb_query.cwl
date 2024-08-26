#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

baseCommand: cat # python3

requirements:
  NetworkAccess: 
    networkAccess: True

intent: [ http://edamontology.org/operation_2421 ] # Database search

hints:
  # DockerRequirement:
  #   dockerPull: nyurik/alpine-python3-requests@sha256:e0553236e3ebaa240752b41b8475afb454c5ab4c17eb023a2a904637eda16cf6
  SoftwareRequirement:
    packages:
      python3:
        version: [ 3.9.5 ]
      requests:
        version: [ 2.25.1 ]

arguments:
 # - $(inputs.script.path)
   - $(inputs.pdb_search_query.path)
 # - "--outpath"
 # - $(inputs.return_file)

stdout: $(inputs.return_file)

inputs:
  script:
    type: File
    default:
      class: File
      location: ./pdb_query.py
  pdb_search_query:
    type: File
    label: Query for PDB search API in json format
    format: iana:application/json
  return_file:
    type: string
    label: Path to output file
    default: "./pdb_ids.txt"
    doc: "Comma-separated text file with PDB ids"

outputs:
  processed_response:
    type: File
    format: iana:text/csv
    doc: Comma-separated text file with returned identifiers from PDB search API
    outputBinding:
       glob: $(inputs.return_file)

# label: Query PDB search API and store output in comma-separated text file.

doc: |
  This tool invokes a Python script which uses requests library to query PDB search API and return a comma-separated file of identifiers returned by the API.
  More information about PDB search API: https://search.rcsb.org/index.html


$namespaces:
  iana: https://www.iana.org/assignments/media-types/
  s: https://www.schema.org/

$schemas:
- https://schema.org/version/latest/schemaorg-current-https.rdf

s:author:
- s:identifier: https://orcid.org/0000-0003-0902-0086

s:mainEntity:
  s:author:
  - s:identifier: https://orcid.org/0000-0003-0902-0086

