cwlVersion: v1.2
class: Workflow

inputs: []

steps:
  step_with_file_default:
    run:
      class: CommandLineTool
      inputs:
        input_with_default:
          type: File
          default:
            class: File
            path: ../../README.rst
          inputBinding: {}
      baseCommand: sha256sum
      outputs: []
    in: []
    out: []

outputs: []
