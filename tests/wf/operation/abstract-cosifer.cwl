class: Operation
cwlVersion: v1.2

requirements:
  DockerRequirement:
    dockerPull: 'docker.io/tsenit/cosifer:b4d5af45d2fc54b6bff2a9153a8e9054e560302e'

inputs:
  data_matrix:
    type: File
  separator:
    type: string?
    doc: The separator used in the data_matrix file
  index_col:
    type: int?
  gmt_filepath:
    type: File?
  outdir:
    type: string?
  samples_on_rows:
    type: boolean?

outputs:
  resdir:
    type: Directory
