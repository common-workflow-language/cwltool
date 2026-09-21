#!/usr/bin/env cwl-runner
# Minimal fixture for exercising cwlprov's ProvenanceProfile.declare_artefact()
# on non-File/Directory dict ("record") and list ("array") job inputs, which
# are otherwise not exercised by any other CWLProv test workflow.
cwlVersion: v1.2
class: CommandLineTool
label: "cwlprov coverage fixture: record + array inputs"
baseCommand: "true"
inputs:
  rec:
    type:
      type: record
      name: rec
      fields:
        - name: a
          type: string
        - name: b
          type: int
  arr:
    type: string[]
outputs: []
