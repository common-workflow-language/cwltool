class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Destination is an expression
inputs:
  sendTo:
    type: string
    default: "bar/"
outputs:
  bar:
    type: File
    outputBinding:
      glob: foo
hints:
  cwltool:OutputDestination:
    destinations:
      bar: $(inputs.sendTo)
arguments: [touch, foo]
