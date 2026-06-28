#!/usr/bin/env cwl-runner
# Companion fixture for https://github.com/common-workflow-language/cwltool/issues/779
# A boolean input with `default: true` must also NOT be a required CLI argument.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  a_bool:
    type: boolean
    default: true
    inputBinding:
      prefix: --a_bool
outputs: []
baseCommand: echo
