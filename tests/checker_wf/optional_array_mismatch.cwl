cwlVersion: v1.0
class: Workflow
inputs:
  first_wf_input: string[]?

steps:
  first_step:
    run:
      class: CommandLineTool
      inputs:
        first_clt_input:
          type: File[]?
          inputBinding:
            position: 1
      baseCommand: [ ls, -l ]
      outputs: []
    in:
      first_clt_input: first_wf_input
    out: []

outputs: []
