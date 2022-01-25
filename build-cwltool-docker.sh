#!/bin/bash
set -ex
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool_module --target module .
docker build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool .

docker run -it -v /var/run/docker.sock:/var/run/docker.sock \
	-v /tmp:/tmp \
	-v "$PWD":/tmp/cwltool \
	quay.io/commonwl/cwltool_module /bin/sh -c \
	"apk add gcc bash && pip install -r/tmp/cwltool/test-requirements.txt ; pytest -k 'not (test_bioconda or test_double_overwrite or test_env_filtering or test_biocontainers or test_disable_file_overwrite_without_ext or test_disable_file_creation_in_outdir_with_ext or test_write_write_conflict or test_directory_literal_with_real_inputs_inside or test_revsort_workflow or test_stdin_with_id_preset)' --ignore-glob '*test_udocker.py' -n auto -v -rs --pyargs cwltool"

version=$(git describe --tags)
if echo "$version" | grep -vq '\-' >& /dev/null ; then
    docker tag quay.io/commonwl/cwltool_module quay.io/commonwl/cwltool_module:"$version"
    docker tag quay.io/commonwl/cwltool quay.io/commonwl/cwltool:"$version"
fi
