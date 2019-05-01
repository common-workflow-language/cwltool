#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow

inputs:
  first_input: File
  second_input:
    type: long
    default: 1337

steps: []

outputs:
  first_output:
    type: File
    outputSource: first_input
    cwlprov:relationships:
       prov:wasDerivedFrom: [ '#first_input' ]
       prov:wasInfluencedBy: [ '#second_input' ]

$namespaces:
  prov: http://www.w3.org/ns/prov#
  cwlprov: https://w3id.org/cwl/prov#

$schemas:
  - http://www.w3.org/ns/prov.owl