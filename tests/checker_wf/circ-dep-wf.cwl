#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: Workflow

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
      intxt: wc/wctxt
    out: [cattxt]
  ls:
    run: ls.cwl
    in:
      intxt: cat-a/cattxt
    out: [lstxt]
  wc:
    run: wc.cwl
    in:
      intxt: ls/lstxt
    out: [wctxt]
