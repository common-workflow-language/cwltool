cwlVersion: v1.1
class: CommandLineTool
requirements:
  ShellCommandRequirement: {}
inputs: []
outputs:
  code:
    type: int
    outputBinding:
      outputEval: $(runtime.exitCode)
successCodes: [7]
arguments: ["exit", "7"]
