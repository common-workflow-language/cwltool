#!/usr/bin/env cwl-runner
{
      "$graph": [
        {
          "class": "Workflow",
          "requirements": [
            {
              "loadListing": "no_listing",
              "class": "http://commonwl.org/cwltool#LoadListingRequirement"
            }
          ],
          "inputs": [
            {
              "type": "Directory",
              "id": "#main/d"
            }
          ],
          "steps": [
            {
              "in": [
                {
                  "source": "#main/d",
                  "id": "#main/step1/d"
                }
              ],
              "out": [
                "#main/step1/out"
              ],
              "run": "#16169-step.cwl",
              "id": "#main/step1"
            }
          ],
          "outputs": [
            {
              "type": "File",
              "outputSource": "#main/step1/out",
              "id": "#main/out"
            }
          ],
          "id": "#main",
          "$namespaces": {
            "cwltool": "http://commonwl.org/cwltool#"
          }
        },
        {
          "class": "CommandLineTool",
          "requirements": [
            {
              "dockerPull": "docker.io/debian:stretch-slim",
              "class": "DockerRequirement",
            },
            {
              "class": "InlineJavascriptRequirement"
            }
          ],
          "inputs": [
            {
              "type": "Directory",
              "id": "#16169-step.cwl/d"
            }
          ],
          "outputs": [
            {
              "type": "stdout",
              "id": "#16169-step.cwl/out"
            }
          ],
          "stdout": "output.txt",
          "arguments": [
            "echo",
            "${if(inputs.d.listing === undefined) {return 'true';} else {return 'false';}}"
          ],
          "id": "#16169-step.cwl"
        }
      ],
      "cwlVersion": "v1.0"
    }
