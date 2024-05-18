#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

baseCommand: python3

doc: "Model training."
intent: [ http://edamontology.org/operation_2423 ]
hints:
  SoftwareRequirement:
    packages:
      python:
        version: [ "3.9" ]
      tqdm:
        specs: [ https://pypi.org/project/tqdm/ ]
        version: [ "4.64.0" ]
      tensorflow-gpu:
        specs: [ https://pypi.org/project/tensorflow-gpu/ ]
        version: [ 2.9.1 ]
      tensorflow-addons:
        specs: [ https://pypi.org/project/tensorflow-addons/ ]
        version: [ "0.17.1" ]
      numpy:
        version: [ "1.21.5" ]
      click:
        version: [ "8.0.4" ]
      commentjson:
        specs: [ https://pypi.org/project/commentjson/ ]
        version: [ "0.9.0" ]

arguments: 
- $(inputs.script.path)
- $(inputs.config_file.path)
- $(inputs.input_features.path)
- $(inputs.input_labels.path)

inputs:
  script:
    type: File
    default:
      class: File
      location: ./emulated_model.py # this is a placeholder script
  config_file:
    type: File
    default:
      class: File
      location: ../model_example_params.json
    doc: "Configuration file used for the model. Here: standard file, but in real workflow it should be generated from previous steps."
  input_features:
    type: Directory
  input_labels:
    type: Directory

  
stdout: "training_log.txt"

outputs:
  train_log:
    type: stdout
    doc: "Output of the model containing predictions and/or performance on the test set."







