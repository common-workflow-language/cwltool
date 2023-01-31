#!/usr/bin/env cwl-runner
# From:
# - https://github.com/common-workflow-language/cwltool/issues/1765
# - https://github.com/pvanheus/lukasa/blob/99e827e0125cf07621253ae081199298adf7227b/protein_evidence_mapping.cwl
cwlVersion: v1.2
class: Workflow

inputs:
  contigs_fasta:
    label: "Genomic contigs (FASTA)"
    type: File
    format: edam:format_1929
outputs:
  out:
    type: File
    outputSource:
      samtools_index_contigs/sequences_with_index

steps:
  samtools_index_contigs:
    # This step is from an external file. print_deps failed here, with a validation
    # error message, even though --validate passed.
    run: bio-cwl-tools:samtools/samtools_faidx.cwl
    in:
      sequences: contigs_fasta
    out:
      - sequences_with_index
$namespaces:
  edam: http://edamontology.org/
  bio-cwl-tools: https://raw.githubusercontent.com/common-workflow-library/bio-cwl-tools/release/
$schemas:
  - http://edamontology.org/EDAM_1.18.owl
