cwlVersion: v1.0.dev4
class: CommandLineTool
inputs:
  schema:
    type: File
    inputBinding: {position: 1}
  target: string
outputs:
  out: stdout
  targetdir:
    type: string
    outputBinding:
      outputEval: $(inputs.target.match(/^([^/]+)\/[^/]/)[1])
baseCommand: [python, "-mschema_salad", "--print-rdfs"]
stdout: $(inputs.target)
