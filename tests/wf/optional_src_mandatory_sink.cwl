#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow

inputs:
 opt_file: File?

steps:
 my_only_step:
   run: ./cat.cwl
   in:
     r: opt_file
   out: []

outputs: []
