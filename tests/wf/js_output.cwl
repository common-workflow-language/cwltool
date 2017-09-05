class: CommandLineTool
cwlVersion: v1.0
requirements:
  - class: InlineJavascriptRequirement
  - class: ShellCommandRequirement
inputs: []
outputs: []
arguments:
  - valueFrom: ${console.log("Log message");console.error("Error message");return "(exit 0)"}
    shellQuote: false