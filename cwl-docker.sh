#!/bin/sh
docker run --name=cwl-docker -v /var/lib/docker -i -t fedora-data true
docker run -v /var/run/docker.sock:/var/run/docker.sock -ti --volume=/tmp:/tmp  --volume="$PWD":"$PWD" -w="$PWD" commonworkflowlanguage/cwltool "$@"
