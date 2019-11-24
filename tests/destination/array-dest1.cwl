class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Destination applies to each element of array output
inputs: []
outputs:
  bar:
    type: File[]
    outputBinding:
      glob: "foo*"
hints:
  cwltool:OutputDestination:
    destinations:
      bar: bar/
arguments: [touch, foo1, foo2]
