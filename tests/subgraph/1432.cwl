class: Workflow
cwlVersion: v1.2
inputs:
  - id: step1_in
    type: string
  - id: step2_in
    type: string
outputs:
  - id: step1_out
    type: string
    outputSource: step1/out
  - id: step2_out
    type: string
    outputSource: step2/out
steps:
  - id: step1
    in:
      - id: inp
        source: step1_in
    out:
      - id: out
    run: ../echo.cwl
  - id: step2
    in:
      - id: inp
        source: step2_in
    out:
      - id: out
    run: ../echo.cwl
