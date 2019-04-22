#!/bin/sh
# Changing the line below? Update https://cloud.docker.com/u/commonworkflowlanguage/repository/docker/commonworkflowlanguage/cwltool
exec docker run -v /var/run/docker.sock:/var/run/docker.sock -v /tmp:/tmp -v "$PWD":"$PWD" -w="$PWD" commonworkflowlanguage/cwltool "$@"
