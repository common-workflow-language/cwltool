#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
inputs: []
outputs:
  file1:
    type: File
    outputSource: step1/file1


steps:
  step1:
    in: []
    out:
      - file1
      - file1csv
    run:
      class: CommandLineTool
      requirements:
      - class: ShellCommandRequirement
      arguments:
      - shellQuote: false
        valueFrom: >
          echo "abc" > f.txt;
          echo "3" > f.txt.size;
          echo "a" > f.txt.firstletter;
          echo "a,b,c" > f.csv;
          echo "1,2,3" > f.csv.columns;
          echo "ignored" > f.txt.ignoreme;
      inputs: []
      outputs:
        file1:
          type: File
          outputBinding:
            glob: "f.txt"
          secondaryFiles:
            - ".size"
            - ".firstletter"
            - "^.csv"
        file1csv:
            type: File
            outputBinding:
              glob: "f.csv"
            secondaryFiles:
            - ".columns"
