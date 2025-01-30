#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  InlineJavascriptRequirement: {}
  cwltool:Loop:
    loopWhen: $(inputs.i1 < 10)
    loop:
      i1: o1
    outputMethod: last
baseCommand: [echo]
arguments:
  - position: 1
    valueFrom: ${ return "$((" + inputs.i1 + " + " + inputs.i2 + "))" )
inputs:
  i1: int
  i2: int
outputs:
  o1:
    type: int
    outputBinding:
      glob: out.txt
      loadContents: true
      outputEval: $(self[0].contents)
stdout: out.txt

