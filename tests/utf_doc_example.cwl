#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  sequenceFile:
    label: "Sequence file in FASTA format"
    doc: |
          Input sequence file in FASTA format (not compressed/zipped!).
          Can be an assembled genome (genome mode) or transcriptome (DNA,
          transcriptome mode), or protein sequences from an annotated gene set
          (proteins mode).
          NB: select just one transcript/protein per gene for your input,
          otherwise they will appear as ‘Duplicated’ matches.
    # note the "smart quotes" around the word Duplicated above, they are
    # non-ASCII
    type: string
baseCommand: echo

outputs: []

