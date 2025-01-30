#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.2

requirements:
  ToolTimeLimit:
    timelimit: 5
  InlineJavascriptRequirement: {}

inputs:
  i:
    type: string?

outputs:
  o:
    type: string?
    outputSource: step2/o

steps:
  step1:
    in:
      i: i
    out: [o]
    run:
      class: CommandLineTool
      baseCommand: ["sleep", "3"]
      inputs:
        i:
          type: string?
      outputs:
        o:
          type: string?
          outputBinding:
            outputEval: $("time passed")
  step2:
    in:
      i: step1/o
    out: [o]
    run:
      class: CommandLineTool
      baseCommand: ["sleep", "3"]
      inputs:
        i:
          type: string?
      outputs:
        o:
          type: string?
          outputBinding:
            outputEval: $("time passed")
