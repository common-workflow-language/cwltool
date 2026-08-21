#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow
requirements:
  StepInputExpressionRequirement: {}
  InlineJavascriptRequirement: {}
inputs:
  files:
    type:
      type: array
      items: File
outputs:
  data_json:
    type: File
    outputSource: merge_data/data_json
steps:
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
        source: files
        loadContents: true
        valueFrom: |
          ${
            const data = [];
            for (let i = 0; i < self.length; i++) {
              const file_data = self[i].contents.trim().split(/\s+/).map(parseFloat);
              data.push(...file_data);
            }
            return data;
          }
    out: [data_json]
