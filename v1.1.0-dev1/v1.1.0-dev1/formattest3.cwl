$namespaces:
  edam: http://edamontology.org/
  gx: http://galaxyproject.org/formats/
$schemas:
  - EDAM.owl
  - gx_edam.ttl
class: CommandLineTool
cwlVersion: v1.1.0-dev1
doc: "Reverse each line using the `rev` command"
hints:
  DockerRequirement:
    dockerPull: "debian:stretch-slim"

inputs:
  input:
    type: File
    inputBinding: {}
    format: gx:fasta

outputs:
  output:
    type: File
    outputBinding:
      glob: output.txt
    format: $(inputs.input.format)

baseCommand: rev
stdout: output.txt
