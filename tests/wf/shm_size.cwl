#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2
requirements:
  cwltool:ShmSize:
    shmSize: 128m
inputs: []

outputs:
  output:
    type: stdout

baseCommand: echo

stdout: shm-size.txt

arguments: [ $(runtime) ]
