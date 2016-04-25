#!/usr/bin/env cwl-runner
class: CommandLineTool

requirements:
  - class: InlineJavascriptRequirement

inputs:
    - { id: "#file1", type: {type: array, items: File}, inputBinding: {} }
outputs:
    - id: "#output"
      type: int
      outputBinding:
        glob: output.txt
        loadContents: true
        outputEval: |
              ${
                var s = self[0].contents.split(/\r?\n/);
                return parseInt(s[s.length-2]);
              }
stdout: output.txt
baseCommand: wc
