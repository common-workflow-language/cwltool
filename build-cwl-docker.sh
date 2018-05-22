#!/bin/sh
set -e
docker build --file=cwltool_module.Dockerfile --tag=commonworkflowlanguage/cwltool_module .
docker build --file=cwltool.Dockerfile --tag=commonworkflowlanguage/cwltool .
