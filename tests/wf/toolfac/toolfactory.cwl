cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
class: ToolFactory
inputs: {}
outputs: {}
run:
  class: CommandLineTool
  inputs:
    processSource: File
  outputs:
    runProcess:
      type: File
      outputBinding:
        glob: main.cwl
    runInputs:
      type: Any
      outputBinding:
        outputEval: $(inputs)
  arguments: [$(inputs.processSource)]
  stdout: main.cwl
