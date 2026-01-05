#!/usr/bin/env cwl-runner
cwlVersion: v1.3.0-dev1
class: Workflow
requirements:
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}
inputs:
  limit: 
    type: int 
    default: 5

outputs:
  - id: result
    type: string[]
    outputSource: step1/result

steps:
  step1:
    run: 
      class: CommandLineTool
      inputs:
        lfile: 
          type: File
          inputBinding:
            position: 1
      stdout: "out.txt"
      outputs:
        result: 
          type: string
          outputBinding:
            glob: "out.txt"
            loadContents: true
            outputEval: $(self[0].contents)-$(self[0].checksum)
      baseCommand: ["cat"]
    in:
      counter: 
        default: 0
      limit: limit
      lfile:
        valueFrom: "${return {'class': 'File', 'basename': 'init-value-from.' + inputs.counter, 'contents': 'first,' + inputs.counter  }}"
    out:
      - id: result
    when: $(inputs.counter < inputs.limit)
    loop:
      counter:
        valueFrom: $(inputs.counter + 1)
    outputMethod: all_iterations