#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  a_record:
    type:
      - "null"
      - type: record
        fields:
          first: string
          second: int
          third: float
          fourth: long
          fifth: double
          sixth: File
    default:
      first: y
      second: 23
      third: 2.3
      fourth: 4242424242
      fifth: 4200000000000000000000000000000000000000000
      sixth:
        class: File
        path: whale.txt
arguments:
 - '{'
 - '"same_record": $(inputs.a_record)'
 - '}'
outputs:
  same_record:
    type:
      type: record
      fields:
        first: string
        second: int
        third: float
        fourth: long
        fifth: double
        sixth: File
baseCommand: echo
stdout: cwl.output.json
