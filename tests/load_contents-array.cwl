cwlVersion: "v1.2"
class: CommandLineTool
baseCommand: echo
requirements:
  InlineJavascriptRequirement: {}
inputs:
  files:
    type:
      type: array
      items: File
    loadContents: true
    inputBinding:
      valueFrom: |
        ${
          return JSON.stringify({
            "data": inputs.files.map(item => parseInt(item.contents))
          });
        }
outputs:
  out:
    type: File
    outputBinding:
      glob: "data.json"
stdout: "data.json"
