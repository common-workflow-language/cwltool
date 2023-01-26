cwlVersion: v1.2
class: Workflow

inputs:
  - id: hello
    type: Any
outputs: []

steps:
  step:
    id: step
    run: schemadef-tool-12.cwl
    in:
      hello: hello
    out: []
