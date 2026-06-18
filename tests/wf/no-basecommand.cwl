#!/usr/bin/env cwl-runner
# Regression fixture for https://github.com/common-workflow-language/cwltool/issues/1618
# A CommandLineTool with no baseCommand/arguments/input bindings produces an empty
# command line; running it should fail with a clear error, not a raw IndexError.
cwlVersion: v1.2
class: CommandLineTool
inputs: []
outputs: []
