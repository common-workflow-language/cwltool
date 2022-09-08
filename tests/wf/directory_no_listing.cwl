#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow

doc: >
    Inspect provided directory and return filenames.
    Generate a new directory and return it (including content).

hints:
  - class: DockerRequirement
    dockerPull: docker.io/debian:stable-slim

inputs:
    dir:
        type: Directory
        loadListing: deep_listing
    ignore:
        type: Directory
        loadListing: no_listing

steps:
    ls:
        in:
            dir: dir
            ignore: ignore
        out:
            [listing]
        run:
            class: CommandLineTool
            baseCommand: ls
            inputs:
                dir:
                    type: Directory
                    inputBinding:
                        position: 1
                ignore:
                    type: Directory
                    inputBinding:
                        position: 2
            outputs:
                listing:
                    type: stdout

    generate:
        in: []
        out:
            [dir1]
        run:
            class: CommandLineTool
            requirements:
                ShellCommandRequirement: {}
                LoadListingRequirement:
                    loadListing: deep_listing

            arguments:
            - shellQuote: false
              valueFrom: >
                    pwd;
                    mkdir -p dir1/a/b;
                    echo -n a > dir1/a.txt;
                    echo -n b > dir1/a/b.txt;
                    echo -n c > dir1/a/b/c.txt;
            inputs: []
            outputs:
                dir1:
                    type: Directory
                    outputBinding:
                        glob: "dir1"

outputs:
    output_1:
        type: File
        outputSource: ls/listing
    output_2:
        type: Directory
        outputSource: generate/dir1

