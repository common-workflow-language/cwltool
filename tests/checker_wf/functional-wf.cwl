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
  echo_w:
    run: echo.cwl
    in:
      echo_in: letters0
    out: [txt]
  echo_x:
    run: echo.cwl
    scatter: echo_in
    in:
      echo_in:
        source: [letters1, letters2]
        linkMerge: merge_nested
    out: [txt]
  echo_y:
    run: echo.cwl
    scatter: echo_in
    in:
      echo_in:
        source: [letters3, letters4]
        linkMerge: merge_flattened
    out: [txt]
  echo_z:
    run: echo.cwl
    in:
      echo_in:
        source: letters5
        valueFrom: "special value parsed in valueFrom"
    out: [txt]
  cat:
    run: cat.cwl
    in:
      cat_in:
        source: [echo_w/txt, echo_x/txt, echo_y/txt, echo_z/txt]
        linkMerge: merge_flattened
    out: [txt]
