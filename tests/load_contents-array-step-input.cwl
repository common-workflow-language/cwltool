#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow
requirements:
  StepInputExpressionRequirement: {}
  InlineJavascriptRequirement: {}
inputs: {}
outputs:
  data_json:
    type: File
    outputSource: merge_data/data_json
steps:
  produce_data:
    run:
      class: CommandLineTool
      baseCommand: ["sh", "-c"]
      arguments:
        - |
          printf '1' > data.txt
          printf '2' > data2.txt
      inputs: {}
      outputs:
        data_files:
          type:
            type: array
            items: File
          outputBinding:
            glob: "*.txt"
    in: {}
    out: [data_files]
  merge_data:
    run:
      class: CommandLineTool
      baseCommand: ["sh", "-c"]
      arguments:
        - |
          printf '{"data": %s}\n' '$(JSON.stringify(inputs.data))' > data.json
      inputs:
        data:
          type: float[]
      outputs:
        data_json:
          type: File
          outputBinding:
            glob: data.json
    in:
      data:
        source: produce_data/data_files
        loadContents: true
        valueFrom: |
          ${
            const data = [];
            for (let i = 0; i < self.length; i++) {
              if (self[i].class !== "File") {
                throw new Error("Expected a File object, but got: " + JSON.stringify(self[i]));
              }
              const file_data = self[i].contents.trim().split(/\s+/).map(parseFloat);
              data.push(...file_data);
            }
            return data;
          }
    out: [data_json]
