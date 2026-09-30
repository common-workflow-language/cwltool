# Original file: tests/eager-eval-reqs-hints/wf-reqs.cwl
# From: https://github.com/common-workflow-language/cwl-v1.2/pull/195
cwlVersion: v1.2
class: Workflow

requirements:
  ResourceRequirement:
    coresMax: $(inputs.threads_max)

inputs:
  threads_max:
    type: int
    default: 2

steps:
  one:
    in: []
    run:
      class: CommandLineTool
      inputs:
        other_input:
          type: int
          default: 8
      baseCommand: echo
      arguments: [ $(runtime.cores) ]
      stdout: out.txt
      outputs:
        out:
          type: string
          outputBinding:
            glob: out.txt
            loadContents: true
            outputEval: $(self[0].contents)
    out: [out]

outputs:
  out:
    type: string
    outputSource: one/out
