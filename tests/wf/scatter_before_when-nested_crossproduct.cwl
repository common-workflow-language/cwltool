cwlVersion: v1.2
class: Workflow

requirements:
  ScatterFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}

inputs:
  messages:
    type:
      - "null"
      - type: array
        items: [string, "null"]
  extras:
    type:
      - "null"
      - type: array
        items: [string, "null"]

steps:
  optional_echo_scatter:
    when: $(inputs.messages !== null && inputs.extra !== null)
    run: ../echo.cwl
    scatter: [messages, extra]
    scatterMethod: nested_crossproduct
    in:
      extra: extras
      messages: messages
      inp:
        valueFrom: $(inputs.messages) $(inputs.extra)
    out: [out]

outputs:
  optional_echoed_messages:
    type: string[]?
    pickValue: all_non_null
    outputSource: optional_echo_scatter/out
