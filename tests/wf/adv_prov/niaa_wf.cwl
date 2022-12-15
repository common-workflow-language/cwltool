#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: Workflow

intent: [ edam:operation_2423 ]  # Prediction ope
doc: "This mock workflow calculates input features and labels which are used to train a deep learning model for epitope prediction."

requirements:
  ScatterFeatureRequirement: {}
  StepInputExpressionRequirement: {}
  SubworkflowFeatureRequirement: {}

inputs: 
  sabdab_summary: 
    type: File
    format: iana:text/tab-separated-values
    doc: "SAbDAb Summary metadata about all structures in the database."
  biodl_train_dataset: 
    type: File
    format: iana:text/csv
    doc: "BioDL training dataset containing PPI interactions"
  biodl_test_dataset: 
    type: File
    doc: "BioDL test dataset with PPI interactions."
  hhblits_db:
    type: Directory
    doc: "Reference database for HHblits"
  hhblits_db_name: 
    type: string
    doc: "Name of hhblits reference database"
  pdb_search_api_query: 
    type: File
    format: iana:application/json
    doc: "Structured query for PDB API."

outputs: 
  model_output:
    type: File
    outputSource: train_epitope_prediction_model/train_log
    doc: "Output of the prediction model."

steps:
  run_pdb_query:
    in:
      pdb_search_query: pdb_search_api_query
    out:
      [ processed_response ]
    run: ./tools/pdb_query.cwl
    doc: |
      Use PDB search API to run a query on the Protein Data Bank. Returns .txt file with comma-separated PDB IDs which satisfy the query requirements.
      See https://search.rcsb.org/index.html#search-api for a tutorial.

  download_pdb_files:
    in: 
      input_file: run_pdb_query/processed_response 
      mmcif_format: { default: True }
      pdb_format: { default: True }
    out:
      [ pdb_files ]
    run: ./tools/pdb_batch_download.cwl
  
  decompress_pdb_files:
    in:
      pdb_archives: download_pdb_files/pdb_files
    out: [ cifs, pdbs ]
    run: ./tools/decompress.cwl
    doc: "Decompress files using gzip"

  generate_dssp_labels:
    in:
      pdb_files: decompress_pdb_files/pdbs # change this later
      rsa_cutoff: { default :  0.06 }
    out: [ dssp_output_files ]
    run: ./tools/dssp.cwl
    doc: "Use DSSP to extract secondary structure and solvent accessibility from PDB files."

  generate_ppi_labels:
    in:
      mmcif_files: decompress_pdb_files/cifs
      train_dataset: biodl_train_dataset
      test_dataset: biodl_test_dataset
    out: [ ppi_fasta_files ]
    run: ./tools/ppi_annotations.cwl
    doc: "Extract ppi annotations from BioDL. This step is partly emulated."
  
  preprocess_sabdab_data:
    doc: "Extract antigen chains from SAbDab summary file."
    in:
      sabdab_summary: sabdab_summary
    out: [ processed_summary ]
    run: ./tools/process_sabdab.cwl

  generate_epitope_labels:
    in: 
      mmcif_files: decompress_pdb_files/cifs
      sabdab_processed: preprocess_sabdab_data/processed_summary
    out: [ epitope_fasta_dir ]
    run: ./tools/epitope_annotations.cwl
    doc: "Extract epitope annotations from PDB files."

  combine_labels:
    doc: "Combine labels into 1 file per protein sequence."
    run: ./tools/combine_labels.cwl
    in:
      epitope_directory: generate_epitope_labels/epitope_fasta_dir
      ppi_directory: generate_ppi_labels/ppi_fasta_files
      dssp_directory: generate_dssp_labels/dssp_output_files
    out: [ labels_combined ]
  
  generate_pc7:
    doc: Calculate PC7 features for each residue in each protein sequence.
    run: ./tools/pc7_inputs.cwl # to do: adapt tool so it takes directory of fasta files as input
    in: 
      fasta: generate_ppi_labels/ppi_fasta_files 
    out: [ pc7_features ]  

  generate_psp19:
    label: Calculate PSP19 features for each residue in each protein sequence.
    run: ./tools/psp19_inputs.cwl
    in:
      fasta: generate_ppi_labels/ppi_fasta_files
    out: [ psp19_features ]

  generate_hhm:
    in:
      query_sequences: 
        source: generate_ppi_labels/ppi_fasta_files # type Directory
        valueFrom: $(self.listing) # here type Directory is converted to File array
      hhblits_db: hhblits_db
      hhblits_db_name: hhblits_db_name
      hhblits_n_iterations: { default: 1 }
    out: [ hhm_file_array ]
    run:
      class: Workflow # this is a subworkflow as a workaround because generate_ppi_labels/ppi_fasta_files is Directory while run_hhblits takes File
      inputs:
        query_sequences: File[]
        hhblits_db: Directory
        hhblits_db_name: string
        hhblits_n_iterations: int
      outputs:
        hhm_file_array:
          type: File[]
          outputSource: run_hhblits/hhm
      steps:
        run_hhblits:
          in: 
            protein_query_sequence: query_sequences
            database: hhblits_db
            database_name: hhblits_db_name
            n_iterations: hhblits_n_iterations
          out: [ hhm ]
          scatter: protein_query_sequence
          run: ./tools/hhm_inputs_scatter.cwl
  combine_features:
    in: 
      input_sequences: generate_ppi_labels/ppi_fasta_files
      pc7_features: generate_pc7/pc7_features
      psp19_features: generate_psp19/psp19_features
      hhm_features: generate_hhm/hhm_file_array # file array, combine_features.cwl converts it to directory
    out: [ combined_features ]
    run: ./tools/combine_features.cwl  
  
  train_epitope_prediction_model: # This step incorporates both training and prediction, not sure if this is the case in the real workflow.
    in: # in the real workflow, the configuration file would be generated as part of the workflow as well
      input_features: combine_features/combined_features
      input_labels: combine_labels/labels_combined
    out: [ train_log ] 
    run: ./tools/train_epitope_model.cwl
    doc: "Predict epitope residues using a multi-task learning approach. This step is not real yet."  

$namespaces:
  iana: "https://www.iana.org/assignments/media-types/"
  s: "https://schema.org/"
  edam: "http://edamontology.org/"
  cwlprov: "https://w3id.org/cwl/prov#"

$schemas:
- https://schema.org/version/latest/schemaorg-current-https.rdf
- https://edamontology.org/EDAM_1.25.owl

s:author:
- s:name: "Renske de Wit"
  s:identifier: https://orcid.org/0000-0003-0902-0086
- s:name: "Katharina Waury"
s:license: https://spdx.org/licenses/Apache-2.0
