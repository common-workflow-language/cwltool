cwlVersion: v1.2
class: Workflow

doc: |
  Implementation of http://www.workflowpatterns.com/patterns/control/structural/wcp10.php#fig13
  the example for the "Arbitrary Cycles" pattern from the Workflow Patterns Initiative

$namespaces:
  cwltool: "http://commonwl.org/cwltool#"

requirements:
  SubworkflowFeatureRequirement: {}

inputs:
  i1: boolean
outputs:
  o1:
    type: Any
    outputSource: subworkflow/o1
steps:
  A:
    in:
      i1: i1
    run:
      class: ExpressionTool
      requirements:
        InlineJavascriptRequirement: {}
      inputs:
        i1: boolean
      expression: |
        ${
           if (inputs.in1) {
              return {"p1": 42, "p2": null};
           }
           return {"p1": null, "p2": 23};
         }
      outputs:
        p1: int?
        p2: int?
    out: [p1, p2]
  B:
    in:
      p1: A/p1
    when: $(inputs.p1 !== null)
    run:
      class: ExpressionTool
      requirements:
        InlineJavascriptRequirement: {}
      inputs:
        p1: int
      expression: |
        ${ return {"p3": inputs.p1 * 2}; }
      outputs:
        p3: int
    out: [p3]
  C:
    in:
      p2: A/p2
    when: $(inputs.p2 !== null)
    run:
      class: ExpressionTool
      requirements:
        InlineJavascriptRequirement: {}
      inputs:
        p2: int
      expression: |
        ${ return {"p4": inputs.p2 * 3 }; }
      outputs:
        p4: int
    out: [p4]
  subworkflow:
    in:
      loop_p3: B/p3
      p4: C/p4
    requirements:
      cwltool:Loop:
        loop_when: $(outputs.o1 !== null)
        loop:
          p3: new_p3
        outputMethod: last
    run:
      class: Workflow
      inputs:
        loop_p3: int?
        p4: int?
      outputs:
        o1:
          type: int
          outputSource: E/o1
        new_p3:
          type: int?
          outputSource: F/end_p3
      steps:
        D:
          in:
            start_p3: loop_p3
          when: $(inputs.p3 !== null)
          run:
            class: ExpressionTool
            requirements:
              InlineJavascriptRequirement: {}
            inputs:
              start_p3: int
            expression: |
              ${ return {"p4": inputs.start_p3 * 10 }; }
            outputs:
              p4: int
          out: [p4]
        E:
          in:
            p4:
              source:
              - p4
              - D/p4
              pickValue: the_only_non_null
          run:
            class: ExpressionTool
            requirements:
              InlineJavascriptRequirement: {}
            inputs:
              p4: int
            expression: |
              ${ if (inputs.p4 < 100) {
                   return {"o1": null, "p5": inputs.p4 };
                 }
                 return {"o1": inputs.p4, "p5": null };
               }
            outputs:
             o1: int?
             p5: int?
          out: [o1, p5]
        F:
          in:
            p5: E/p5
            o1: E/o1
          when: $(inputs.o1 === null)
          run:
            class: ExpressionTool
            requirements:
              InlineJavascriptRequirement: {}
            inputs:
              p5: int
            expression: |
              ${ return {"end_p3": inputs.p5 + 1}; }
            outputs:
              end_p3: int
          out: [end_p3]
    out: [o1, new_p3]
