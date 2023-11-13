#!/bin/bash
set -ex
engine=${ENGINE:-docker}  # example: `ENGINE=podman ./build-cwltool-docker.sh`
${engine} build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool_module --target module .
${engine} build --file=cwltool.Dockerfile --tag=quay.io/commonwl/cwltool .

${engine} run -t -v /var/run/docker.sock:/var/run/docker.sock \
	-v /tmp:/tmp \
	-v "$PWD":/tmp/cwltool \
	quay.io/commonwl/cwltool_module /bin/sh -c \
	"apk add gcc bash git && pip install -r/tmp/cwltool/test-requirements.txt ; pytest -k 'not (test_bioconda or test_double_overwrite or test_env_filtering or test_biocontainers or test_disable_file_overwrite_without_ext or test_disable_file_creation_in_outdir_with_ext or test_write_write_conflict or test_directory_literal_with_real_inputs_inside or test_revsort_workflow or test_stdin_with_id_preset or test_no_compute_chcksum or test_packed_workflow_execution[tests/wf/count-lines1-wf.cwl-tests/wf/wc-job.json-False] or test_sequential_workflow or test_single_process_subwf_subwf_inline_step)' --ignore-glob '*test_udocker.py' -n 0 -v -rs --pyargs cwltool"
