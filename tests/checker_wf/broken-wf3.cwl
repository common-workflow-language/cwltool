#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
requirements:
  ScatterFeatureRequirement: {}
  MultipleInputFeatureRequirement: {}
  StepInputExpressionRequirement: {}
inputs:
  letters0:
    type: [string, int]
    default: "a0"
  letters1:
    type: string[]
    default: ["a1", "b1"]
  letters2:
    type: [string, int]
    default: "a2"
  letters3:
    type: string[]
    default: ["a3", "b3"]
  letters4:
    type: string
    default: "a4"
  letters5:
    type: string[]
    default: ["a5", "b5", "c5"]

outputs:
  all:
    type: File
    outputSource: cat/txt

steps:
  - id: embedded
    run: functional-wf.cwl
    in: []
    out:
     - id: All
  - id: cat
    run: cat.cwl
    in:
      - id: cat_in
        source:
         - embedded/All
    out: [txt]
