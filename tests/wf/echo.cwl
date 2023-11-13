#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
inputs:
  r: string
  script:
    type: string
    default: |
      import sys
      print(sys.argv[1])
      if sys.argv[1] == "2":
        exit(1)
      else:
        f = open("foo"+sys.argv[1]+".txt", "wb")
        content = sys.argv[1]+"\n"
        f.write(content.encode('utf-8'))
      if sys.argv[1] == "5":
        exit(1)
outputs:
  out:
    type: File
    outputBinding:
      glob: foo$(inputs.r).txt
arguments: [python3, -c, $(inputs.script), $(inputs.r)]
