class: CommandLineTool
cwlVersion: v1.0
inputs:
  r: string
  script:
    type: string
    default: |
      import sys
      print sys.argv[1]
      if sys.argv[1] == "2":
        exit(1)
      else:
        f = open("foo"+sys.argv[1]+".txt", "w")
        f.write(sys.argv[1]+"\n")
      if sys.argv[1] == "5":
        exit(1)
outputs:
  out:
    type: File
    outputBinding:
      glob: foo$(inputs.r).txt
arguments: [python, -c, $(inputs.script), $(inputs.r)]