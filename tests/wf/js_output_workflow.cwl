#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0
requirements:
  - class: InlineJavascriptRequirement
inputs: []
outputs: []
steps:
  - id: js_log
    in: []
    out: []
    run: 
      class: ExpressionTool
      inputs: []
      outputs: []
      expression: ${console.log("Log message");console.error("Error message");return ["python", "-c", "True"];}