#!/bin/bash
set -ex
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool_module --target module .
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool .

docker run -v -it /var/run/docker.sock:/var/run/docker.sock \
	-v /tmp:/tmp \
	-v $PWD:/tmp/cwltool \
	quay.io/commonwl/cwltool_module /bin/sh -c \
	"apk add gcc bash && pip install -r/tmp/cwltool/test-requirements.txt ; pytest -k 'not test_bioconda and not test_double_overwrite and not test_env_filtering' -n auto --dist=loadfile --pyargs cwltool"

version=$(git describe --tags)
if echo "$version" | grep -vq '\-' >& /dev/null ; then
    docker tag quay.io/commonwl/cwltool_module quay.io/commonwl/cwltool_module:"$version"
    docker tag quay.io/commonwl/cwltool quay.io/commonwl/cwltool:"$version"
fi
