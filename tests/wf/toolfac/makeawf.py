#!/usr/bin/env python3
print("""
cwlVersion: v1.0
class: CommandLineTool
inputs:
  zing: string
outputs: {}
arguments: [echo, $(inputs.zing)]
""")
