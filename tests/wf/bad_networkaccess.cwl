#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1
requirements:
  InlineJavascriptRequirement: {}
  NetworkAccess:
    networkAccess: '${return 42;}'
inputs: []
outputs: []
baseCommand: echo, Hello, World!
