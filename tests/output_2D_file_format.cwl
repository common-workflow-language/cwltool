#!/usr/bin/env cwl-runner
cwlVersion: v1.0

class: CommandLineTool

baseCommand: 'true'

requirements:
  InlineJavascriptRequirement: {}

inputs: {}

outputs:
  output_array:
    type: {"type": "array", "items": {"type": "array", "items": "File"}}
    outputBinding:
      outputEval: |
        ${
          var out2d = [];
          for (var i = 0; i < 2; i++) {
            var out1d = [];
            for (var j = 0; j < 2; j++) {
              out1d.push({"class": "File", "location": "../../filename.txt"});
            }
            out2d.push(out1d);
          }
          return out2d;
        }
    format: some_format
