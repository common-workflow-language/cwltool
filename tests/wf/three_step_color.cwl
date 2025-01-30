#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: Workflow

requirements:
  SubworkflowFeatureRequirement: {}

inputs:
  file_input: File

outputs: 
  string_output:
    type: string
    outputSource: operation/operation_output
  file_output:
    type: File
    outputSource: command_line_tool/out_file

steps:
  nested_workflow:
    label: "workflow"
    run: 1st-workflow.cwl
    in:
      inp: file_input
      ex:
        default: "Hello.java"
    out: [ classout ]
  operation:
    label: "Operation"
    in: 
      operation_input: nested_workflow/classout
    out: 
      [operation_output]
    run:
      class: Operation
      inputs:
        operation_input: File
      outputs:
        operation_output: string
  command_line_tool:
    in:
      clt_input: operation/operation_output
    out: [ out_file ]
    run:
      class: CommandLineTool
      baseCommand: echo
      arguments:
      - $(inputs.clt_input)
      - ">"
      - "output.txt"
      inputs:
        clt_input:
          type: string
      outputs: 
        out_file:
          type: File
          outputBinding:
            glob: "output.txt"