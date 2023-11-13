#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow

label: "Hello World"
doc: "Outputs a message using echo"

inputs:
  usermessage: string

outputs:
  response:
    outputSource: step0/response
    type: File

hints:
 - {}

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
      arguments:
         - "-n"
         - "-e"
      stdout: response.txt
      outputs:
        response:
          type: stdout
    in:
      message: usermessage
    out: [response]
