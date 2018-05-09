#!/usr/bin/env sh
if [ ! -S /var/run/docker.sock ]; then
  >&2 echo 'ERROR: cwltool cannot work inside a container without access to docker'
  >&2 echo 'Launch the container with the option -v /var/run/docker.sock:/var/run/docker.sock'
  exit 1
elif [ "$PWD" = '/error' ]; then
  >&2 echo 'ERROR: cwltool cannot work without access to the current path'
  >&2 echo 'Launch the container with the options -v "$PWD":"$PWD" -w="$PWD"'
  exit 1
else
  cwltool "$@"
fi
