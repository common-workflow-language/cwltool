#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

requirements:
- class: InlineJavascriptRequirement
- class: InitialWorkDirRequirement
  listing: |
    ${
      return [{"class": "Directory",
               "basename": "default",
               "listing": [{"class": "File",
                            "basename": "file.txt",
                            "contents": "Hello world"}
                           ],
               "writable": true}]
    }

hints:
- class: DockerRequirement
  dockerPull: docker.io/ubuntu

inputs: []

outputs:

  output_folder:
    type: Directory
    outputBinding:
      glob: "*"

baseCommand: [ls]
