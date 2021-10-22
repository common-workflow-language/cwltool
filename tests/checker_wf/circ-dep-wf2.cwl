#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: Workflow
requirements:
  MultipleInputFeatureRequirement: {}

inputs:
  txt:
    type: File
    default:
      class: File
      location: test.txt

outputs:
  wctxt:
    type: File
    outputSource: wc/wctxt

steps:
  cat-a:
    run: cat-a.cwl
    in:
      intxt:
        source: [txt, txt]
        linkMerge: merge_flattened
    out: [cattxt]
  ls:
    run: ls.cwl
    in:
      intxt: ls/lstxt
    out: [lstxt]
  wc:
    run: wc.cwl
    in:
      intxt: ls/lstxt
    out: [wctxt]
