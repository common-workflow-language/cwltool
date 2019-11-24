class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Destination of single file is a directory
inputs: []
outputs:
  bar:
    type: File
    outputBinding:
      glob: foo
hints:
  cwltool:OutputDestination:
    destinations:
      bar: bar/
arguments: [touch, foo]
