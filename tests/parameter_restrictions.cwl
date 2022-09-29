cwlVersion: v1.2
class: CommandLineTool

doc: |
  Tests of paramater restrictions extension

inputs:
  one: double
  two: string
  three: int


hints:
  cwltool:ParameterRestrictions:
    restrictions:
      one:
       - class: cwltool:realInterval
         low: 0
         high: 3
         high_inclusive: false
       - class: cwltool:realInterval
         low: 6
         # high should be the default of positive infinity
         high_inclusive: false
      two:
       - class: cwltool:regex
         rpattern: "foo.*bar"
      three:
       - class: cwltool:intInterval
         low: -10
         high: -7


baseCommand: echo

arguments:
 - $(inputs.one) 
 - $(inputs.two) 

outputs:
  result: stdout

$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

