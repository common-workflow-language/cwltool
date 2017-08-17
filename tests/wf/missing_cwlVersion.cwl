#!/usr/bin/env cwl-runner
class: Workflow

label: "Hello World"
doc: "Outputs a message using echo"

inputs: []

outputs:
  response:
    outputSource: step0/response
    type: File

steps:
  step0:
    run:
      class: CommandLineTool
      inputs:
        message:
          type: string
          doc: "The message to print"
          default: "Hello World"
          inputBinding:
            position: 1
      baseCommand: echo
      stdout: response.txt
      outputs:
        response:
          type: stdout
    in: []
    out: [response]
