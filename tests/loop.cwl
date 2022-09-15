cwlVersion: v1.2
class: Workflow

$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

inputs:
  i1: Any
outputs:
  o1:
    type: Any
    outputSource: subworkflow/o1
steps:
  A:
    run: A.cwl
    in:
      in1: in1
    out: [p1, p2]
  B:
    run: B.cwl
    in:
      p1: A/p1
    out: [p3]
  C:
    run: C.cwl
    in:
      p2: A/p2
    out: [p4]
  subworkflow:
    run:
      class: Workflow
      inputs:
        p3: Any
        p4: Any
      outputs:
        o1:
          type: Any
          outputSource: E/o1
        p3:
          type: Any
          outputSource: F/p3
      steps:
        D:
          run: D.cwl
          in:
            p3: p3
          out: [p4]
        E:
          run: E.cwl
          in:
            p4:
              source:
              - p4
              - D/p4
              pickValue: the_only_non_null
          out: [o1, p5]
        F:
          run: F.cwl
          in:
            p5: E/p5
          out: [p3]
    in:
      p3: B/p3
      p4: C/p4
    out: [o1, p3]
    requirements:
      cwltool:Loop:
        loop_when: $(outputs.o1 !== null)
        loop:
          p3: p3
        outputMethod: last
