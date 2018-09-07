#!/bin/bash
set -e
docker build --file=cwltool.Dockerfile --tag=commonworkflowlanguage/cwltool_module --target module .
docker build --file=cwltool.Dockerfile --tag=commonworkflowlanguage/cwltool .

version=$(git describe --tags)
echo $version | grep -vq '\-' >& /dev/null
if [ $? -eq 0 ];then
    docker tag commonworkflowlanguage/cwltool_module commonworkflowlanguage/cwltool_module:$version
    docker tag commonworkflowlanguage/cwltool commonworkflowlanguage/cwltool:$version
fi
