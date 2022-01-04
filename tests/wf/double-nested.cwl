#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow
label: "Nested workflow example"

inputs: []

outputs:
  classout:
    type: File
    outputSource: compile/classout

requirements:
  - class: SubworkflowFeatureRequirement

steps:
  compile:
    run:
      class: Workflow
      inputs:
        inp2: File
        ex2: string
      steps:
        nested_compile:
          run: 1st-workflow.cwl
          in:
            inp: inp2
            ex: ex2
          out: [classout]
      outputs:
        classout:
          type: File
          outputSource: nested_compile/classout
    in:
      inp2:
        source: create-tar/tar
      ex2:
        default: "Hello.java"
    out: [classout]

  create-tar:
    requirements:
      - class: InitialWorkDirRequirement
        listing:
          - entryname: Hello.java
            entry: |
              public class Hello {
                public static void main(String[] argv) {
                    System.out.println("Hello from Java");
                }
              }
    in: []
    out: [tar]
    run:
      class: CommandLineTool
      requirements:
        - class: ShellCommandRequirement
      arguments:
        - shellQuote: false
          valueFrom: |
            date
            tar cf hello.tar Hello.java
            date
      inputs: []
      outputs:
        tar:
          type: File
          outputBinding:
            glob: "hello.tar"
