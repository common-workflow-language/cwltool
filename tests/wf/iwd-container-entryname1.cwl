cwlVersion: v1.2
class: CommandLineTool
doc: |
  When executing in a container, entryname can have an absolute path
  to a mount location inside the container.
inputs:
  filelist: File
outputs:
  head:
    type: File
    outputBinding:
      glob: head.txt
requirements:
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim
    dockerOutputDirectory: /output
  InitialWorkDirRequirement:
    listing:
      - entryname: /tmp2j3y7rpb/input/stuff.txt  # Give it a weird prefix to minimize chance of conflict with a real file
        entry: $(inputs.filelist)
  ShellCommandRequirement: {}
arguments:
  - {shellQuote: false, valueFrom: "head -n10 /tmp2j3y7rpb/input/stuff.txt > /output/head.txt"}
