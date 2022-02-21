cwlVersion: v1.2
class: CommandLineTool
requirements:
  InlineJavascriptRequirement: {}
   
inputs:
  gtf_version:
    type: string
    default: M21
  organism:
    type: string
    default: mouse
  organism_prefix:
    type: string
    default: m

baseCommand:
  - bash
  - -c
arguments:
  - touch GRC$(inputs.organism_prefix)38.primary_assembly.genome.fa ; touch  gencode.v$(inputs.gtf_version).primary_assembly.annotation.gtf 
outputs:
  - id: references
    type:
        name: References
        fields:
          - name: genome_fa
            type: File
          - name: annotation_gtf
            type: File
        type: record
    outputBinding:
        outputEval: '$({ "genome_fa": { "class": "File", "path": runtime.outdir+"/"+"GRC"
            + inputs.organism_prefix + "38.primary_assembly.genome.fa" }, "annotation_gtf":
            { "class": "File", "path": runtime.outdir+"/"+"gencode.v" + inputs.gtf_version
            + ".primary_assembly.annotation.gtf" } })'
