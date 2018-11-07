#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow

inputs: {}

outputs:
  first_file:
    type: File
    outputSource: first/stdout
  second_file:
    type: File
    outputSource: second/stdout

steps:
  first:
    run: ../echo.cwl
    in:
      inp:
        default: 'foo'
    out: [stdout]

  second:
    run: ../echo.cwl
    in:
      inp:
        default: 'bar'
    out: [stdout]
