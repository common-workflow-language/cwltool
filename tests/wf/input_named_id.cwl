#!/usr/bin/env cwl-runner
label: FeatureFinderIdentification
doc: ""
inputs:
  id:
    doc: featureXML or consensusXML file
    type: File
outputs:
  []
cwlVersion: v1.2
class: CommandLineTool
baseCommand:
  - FeatureFinderIdentification

