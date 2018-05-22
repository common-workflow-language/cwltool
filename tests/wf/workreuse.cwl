class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  DockerRequirement:
    dockerPull: python:3
  cwltool:WorkReuse:
    enableReuse: false
inputs: []
outputs:
  page: stdout
stdout: time.txt
baseCommand: python
arguments:
  - "-c"
  - valueFrom: |
      import time
      print(time.time())