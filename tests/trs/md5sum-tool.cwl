#!/usr/bin/env cwl-runner

class: CommandLineTool
id: Md5sum
label: Simple md5sum tool
cwlVersion: v1.0

$namespaces:
  dct: http://purl.org/dc/terms/
  foaf: http://xmlns.com/foaf/0.1/

requirements:
- class: DockerRequirement
  dockerPull: quay.io/agduncan94/my-md5sum
- class: InlineJavascriptRequirement

hints:
- class: ResourceRequirement
  # The command really requires very little resources.
  coresMin: 1
  ramMin: 1024
  outdirMin: 512

inputs:
  input_file:
    type: File
    inputBinding:
      position: 1
    doc: The file that will have its md5sum calculated.

outputs:
  output_file:
    type: File
    format: http://edamontology.org/data_3671
    outputBinding:
      glob: md5sum.txt
    doc: A text file that contains a single line that is the md5sum of the input file.

baseCommand: [/bin/my_md5sum]