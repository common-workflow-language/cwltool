#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
inputs:
  r: File
outputs: []
arguments: [cat, $(inputs.r.path)]