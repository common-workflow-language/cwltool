class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Array of destinations applies to each element of array separately.
inputs: []
outputs:
  bar:
    type: File[]
    outputBinding:
      glob: "foo*"
hints:
  cwltool:OutputDestination:
    destinations:
      bar: [bar/, baz/]
arguments: [touch, foo1, foo2]
