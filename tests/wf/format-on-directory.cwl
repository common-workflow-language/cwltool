#!/usr/bin/env cwl-runner
# Regression fixture for https://github.com/common-workflow-language/cwltool/issues/1616
# (and #607): `format` is only meaningful for File parameters. Specifying it on a
# Directory input should produce a validation warning, not pass silently.
cwlVersion: v1.2
class: CommandLineTool
inputs:
  indir:
    type: Directory
    format: http://edamontology.org/format_1915
    inputBinding: {}
outputs: []
baseCommand: echo
