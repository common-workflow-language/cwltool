#!/bin/sh
set -e
docker build --file=cwltool.Dockerfile --tag=commonworkflowlanguage/cwltool .
