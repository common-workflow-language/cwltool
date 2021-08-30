#!/usr/bin/env cwltool
{cwl:tool: pytoolgen.cwl, script: {$include: "#attachment-1"}, dir: {class: Directory, location: .}}
--- |
import os
import sys
print("""
cwlVersion: v1.0
class: CommandLineTool
inputs:
  zing: string
outputs: {}
arguments: [echo, $(inputs.zing)]
""")
