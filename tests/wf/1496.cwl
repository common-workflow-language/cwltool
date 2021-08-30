cwlVersion: v1.2
class: CommandLineTool

baseCommand: echo

inputs:
  index:
    type: Directory
    inputBinding: {}

outputs:
  salmon_index:
    type: Directory
    outputBinding:
      glob: "$(inputs.index)"  # not a valid glob, result needs to be a string, not a Directory object
