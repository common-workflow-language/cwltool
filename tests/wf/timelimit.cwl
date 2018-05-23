class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
inputs: []
outputs: []
requirements:
  cwltool:TimeLimit:
    timelimit: 15
baseCommand: [sleep, "3"]
