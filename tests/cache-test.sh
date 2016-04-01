#!/usr/bin/env bash

python ../cwltool/main.py --debug --cache-intermediate-output --tmpdir-prefix=/Users/spanglry/Code/cwltool/tests/ --tmp-outdir-prefix=/Users/spanglry/Code/cwltool/tests/ revsort-workflow.cwl --input revsort-workflow.cwl
