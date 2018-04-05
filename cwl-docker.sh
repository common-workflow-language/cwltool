#!/bin/sh
docker run --name=cwl-docker -v /var/lib/docker -i -t fedora-data true
docker run -ti -v /var/run/docker.sock:/var/run/docker.sock -v /tmp:/tmp -v "$PWD":"$PWD" -w="$PWD" commonworkflowlanguage/cwltool "$@"
