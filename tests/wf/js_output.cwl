#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
requirements:
  - class: InlineJavascriptRequirement
inputs: []
outputs: []
arguments:
  - valueFrom: ${console.log("Log message");console.error("Error message");return ["python", "-c", "True"]}
    shellQuote: false