#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

doc: "Preprocess SAbDab summary file."
intent: [ http://edamontology.org/operation_2409 ]

hints:
  # DockerRequirement:
  #   dockerPull: amancevice/pandas:1.3.4-slim
  SoftwareRequirement:
    packages:
      python:
        version: [ "3.9.7" ]
      pandas:
        version: [ "1.3.4" ]

baseCommand: cat  # python3

arguments:
# - $(inputs.script.path)
  - $(inputs.sabdab_summary.path)
# - "-o"
# - $(inputs.results_name)

stdout:  $(inputs.results_name)

inputs:
  script:
    type: File
    default:
      class: File
      location: ./process_sabdab_summary.py
  sabdab_summary:
    type: File
    label: Summary file downloaded from SAbDab.
    format: iana:text/tab-separated-values
  results_name:
    type: string
    label: Name of output file in which processed results are stored.
    default: "SAbDab_protein_antigens_PDB_chains.csv"

outputs:
  processed_summary:
    type: File
    format: iana:text/csv
    outputBinding:
      glob: $(inputs.results_name)

s:author:
- class: s:Person
  s:name: "Renske de Wit"
  s:identifier: https://orcid.org/0000-0003-0902-0086
s:license: https://spdx.org/licenses/Apache-2.0

s:mainEntity:
  class: s:SoftwareApplication
  s:license: https://spdx.org/licenses/Apache-2.0
  s:author:
  - class: s:Person
    s:name: "Katharina Waury"
    s:identifier: <Kathi's ORCID identifier>

$namespaces:
  iana: "https://www.iana.org/assignments/media-types/"
  s: "https://schema.org/"
