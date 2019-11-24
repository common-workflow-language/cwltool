class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
doc: |
  Single file is renamed
inputs: []
outputs:
  bar:
    type: File
    outputBinding:
      glob: foo
hints:
  cwltool:OutputDestination:
    destinations:
      bar: bar
arguments: [touch, foo]
