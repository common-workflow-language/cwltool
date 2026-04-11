cwlVersion: v1.0
class: Workflow

inputs:
  output_base: string
  records:
    type:
      type: array
      items:
        type: record
        fields:
          fullid: string

steps:
  main_step:
   run:
     class: CommandLineTool
     inputs:
       records:
         type:
           type: array
           items:
             type: record
             fields:
               fullid: string
               missing: string
     outputs: []
     baseCommand: echo
     arguments: [ $(inputs.records) ]

   in:
     records: records
   out: []


outputs: []
