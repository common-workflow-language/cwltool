cwlVersion: v1.2
class: Workflow

requirements:
  ScatterFeatureRequirement: {}
  InlineJavascriptRequirement: {}

inputs:
  messages:
    type:
      - "null"
      - type: array
        items: [string, "null"]

steps:
  optional_echo_scatter:
    when: $(inputs.inp !== null)
    run: ../echo.cwl
    scatter: inp
    in:
      inp: messages
    out: [out]

outputs:
  optional_echoed_messages:
    type: string[]?
    pickValue: all_non_null
    outputSource: optional_echo_scatter/out
