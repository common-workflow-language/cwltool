#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0

inputs:
  file1:
    type: File
  file2:
    type: File
  file3:
    type: File

outputs:
  count_output:
    type: int
    outputSource: step2/output

  output3:
    type: File
    outputSource: step3/output

  output4:
    type: int
    outputSource: step4/output

  output5:
    type: File
    outputSource: step5/output

steps:
  step1:
    run: wc-tool.cwl
    in:
      file1: file1
    out: [output]

  step2:
    run: parseInt-tool.cwl
    in:
      file1: step1/output
    out: [output]

  step3:
    label: step that is independent of step1 and step2
    run: wc-tool.cwl
    in:
      file1: file2
    out: [output]

  step4:
    label: step that also depends on step1
    run: parseInt-tool.cwl
    in:
      file1: step1/output
    out: [output]

  step5:
    label: step with two inputs
    run: wc-tool.cwl
    in:
      file1: file1
      file3: file3
    out: [output]
