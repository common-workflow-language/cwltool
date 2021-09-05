class: Workflow
cwlVersion: v1.2
id: abstract_cosifer_workflow
label: abstract-cosifer-workflow

inputs:
  data_matrix: {type: File, doc: "Gene expression data matrix"}
  gmt_filepath: {type: "File?", doc: "Optional GMT file to perform inference on multiple gene sets"}
  index_col: {type: "int?", doc: "Column index in the data. Defaults to None, a.k.a., no index"}
  outdir: {type: string, doc: "Path to the output directory"}
  separator: {type: "string?", doc: "Separator for the data. Defaults to ."}
  samples_on_rows: {type: "boolean?", doc: "Flag that indicates that data contain the samples on rows. Defaults to False."}

outputs:
  resdir: {type: Directory, outputSource: abstract_cosifer/resdir}

steps:
  abstract_cosifer:
    run: abstract-cosifer.cwl
    in:
      data_matrix: data_matrix
      separator: separator
      index_col: index_col
      gmt_filepath: gmt_filepath
      outdir: outdir
      samples_on_rows: samples_on_rows
    out: [resdir]
