#!/usr/bin/env cwl-runner
# Regression fixture for https://github.com/common-workflow-language/cwltool/issues/779
# A boolean input with `default: false` must NOT become a required CLI argument.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  a_bool:
    type: boolean
    default: false
    inputBinding:
      prefix: --a_bool
outputs: []
baseCommand: echo
