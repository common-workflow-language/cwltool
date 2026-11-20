cwlVersion: v1.0
class: Workflow
inputs:
  msg: string
steps:
  step1:
    run: 2217-tool.cwl
    in: {msg: msg}
    out: [out]
  step2:
    run: 2217-tool.cwl
    in: {msg: msg}
    out: [out]
outputs:
  out1: {type: string, outputSource: step1/out}
  out2: {type: string, outputSource: step2/out}
