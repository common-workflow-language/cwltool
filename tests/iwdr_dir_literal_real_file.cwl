class: CommandLineTool
cwlVersion: v1.0

requirements:
  DockerRequirement:
      dockerPull: debian:stable-slim
  InlineJavascriptRequirement: {}
  InitialWorkDirRequirement:
    listing: |
      ${
         return [{"class": "Directory",
                  "basename": "subdir",
                  "listing": [ inputs.example ]
                  }]}

inputs:
  example: File

outputs:
  same:
   type: File
   outputBinding:
     glob: subdir/$(inputs.example.basename)
