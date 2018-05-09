#!/bin/sh
exec docker run -v /var/run/docker.sock:/var/run/docker.sock -v /tmp:/tmp -v "$PWD":"$PWD" -w="$PWD" commonworkflowlanguage/cwltool "$@"
