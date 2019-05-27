#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.1

requirements:
  ToolTimeLimit:
    timelimit: 0
  WorkReuse:
    enableReuse: false

inputs:
  i:
    type: int?

outputs:
  o:
    type: string?
    outputSource: step1/o

steps:
  step1:
    in:
      i: i
    out: [o]
    run:
      class: CommandLineTool
      baseCommand: ["sleep", "10"]
      inputs:
        i:
          type: int?
      outputs:
        o:
          type: string?
          outputBinding:
            outputEval: "time passed"
