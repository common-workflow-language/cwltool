#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:NetworkAccess:
    networkAccess: true
inputs: []
outputs: []
baseCommand: python
arguments:
  - "-c"
  - valueFrom: |
      import urllib.request
      assert(urllib.request.urlopen("http://commonwl.org").code == 200)