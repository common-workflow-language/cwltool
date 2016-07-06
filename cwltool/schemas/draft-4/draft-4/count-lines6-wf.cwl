#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: cwl:draft-4.dev3

inputs:
    file1: File[]
    file2: File[]

outputs:
    count_output:
      type: int[]
      outputSource: step1/output

requirements:
  - class: ScatterFeatureRequirement
  - class: MultipleInputFeatureRequirement

steps:
  step1:
    run: wc3-tool.cwl
    scatter: file1
    in:
      file1:
        source: [file1, file2]
        linkMerge: merge_nested
    out: [output]
