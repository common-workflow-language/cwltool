#!/bin/sh
if ! [ -S /var/run/docker.sock ] && [ -z "$DOCKER_HOST" ]; then
  >&2 echo 'ERROR: cwltool cannot work inside a container without access to docker'
  >&2 echo 'Launch the container with the option -v /var/run/docker.sock:/var/run/docker.sock'
  # shellcheck disable=SC2016
  >&2 echo 'or launch the container with the option to set $DOCKER_HOST'
  exit 1
elif [ "$PWD" = '/error' ]; then
  >&2 echo 'ERROR: cwltool cannot work without access to the current path'
  # shellcheck disable=SC2016
  >&2 echo 'Launch the container with the options -v "$PWD":"$PWD" -w="$PWD"'
  exit 1
else
  cwltool "$@"
fi
