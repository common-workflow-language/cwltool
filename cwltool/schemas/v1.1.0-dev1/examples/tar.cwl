cwlVersion: v1.1.0-dev1
class: CommandLineTool
baseCommand: [tar, xf]
inputs:
  tarfile:
    type: File
    inputBinding:
      position: 1
outputs:
  example_out:
    type: File
    outputBinding:
      glob: hello.txt
