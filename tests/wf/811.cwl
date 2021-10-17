cwlVersion: v1.0
class: Workflow

inputs:
  - id: hello
    type: Any
outputs: []

steps:
  step:
    id: step
    run: schemadef-tool.cwl
    in:
      hello: hello
    out: []
