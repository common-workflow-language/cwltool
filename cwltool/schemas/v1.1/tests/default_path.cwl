cwlVersion: v1.1
class: CommandLineTool
inputs:
  - id: "file1"
    type: File
    default:
      class: File
      path: whale.txt
outputs: []
arguments: [cat,$(inputs.file1.path)]
