#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim
  InitialWorkDirRequirement:
    listing:
      - class: File
        basename: hi.txt
        contents: Hello, World!

inputs: []

baseCommand:
 - cat
 - /var/spool/cwl/hi.txt

stdout: result.txt

outputs:
  result: stdout
