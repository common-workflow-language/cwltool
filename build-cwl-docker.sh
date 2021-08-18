#!/bin/bash
set -ex
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool_module --target module .
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool .

version=$(git describe --tags)
if echo "$version" | grep -vq '\-' >& /dev/null ; then
    docker tag quay.io/commonwl/cwltool_module quay.io/commonwl/cwltool_module:"$version"
    docker tag quay.io/commonwl/cwltool quay.io/commonwl/cwltool:"$version"
fi
