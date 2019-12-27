class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Array of destinations renames each element of array separately.
inputs:
  sendTo:
    type: string
    default: "bar/"
outputs:
  bar:
    type: File[]
    outputBinding:
      glob: "foo*"
hints:
  cwltool:OutputDestination:
    destinations:
      bar: ["$(inputs.sendTo)", "$(inputs.sendTo)baz"]
arguments: [touch, foo1, foo2]
