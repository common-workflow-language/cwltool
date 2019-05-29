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
    tfbash_py:
      type: File
      default:
        class: File
        location: tfbash.py
  outputs:
    runProcess:
      type: File
      outputBinding:
        glob: main.cwl
  arguments: [$(inputs.tfbash_py), $(inputs.processSource)]
  stdout: main.cwl
