#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  first:
    type: string
    inputBinding: {}
  second:
    type: string
    inputBinding: {}
  third:
    type: string
    label: groupless
outputs:
  - id: out
    type: string
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
baseCommand: echo
stdout: out.txt


$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

hints:
  cwltool:Groups:
    groups:
      my_groups:
        groupMembers: [first, second]
        label: my great inputs
        doc: "parameters related to the foobar feature"
