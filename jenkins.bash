#!/usr/bin/bash
cloneorpull() {
        if test -d $1 ; then
                (cd $1 && git pull)
        else
                git clone $2
        fi
}
venv() {
        if ! test -d $1 ; then
                virtualenv $1
        fi
        . $1/bin/activate
}
cloneorpull common-workflow-language https://github.com/common-workflow-language/common-workflow-language.git
venv cwltool-venv
(. cwltool-venv/bin/activate && PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/ pip install -U setuptools wheel pip)
(. cwltool-venv/bin/activate && PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/ python setup.py install)
(. cwltool-venv/bin/activate && PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/ pip install "cwltest>=1.0.20160825151655")
# (. cwltool-venv/bin/activate && cd common-workflow-language && ./run_test.sh --junit-xml=result.xml RUNNER=cwltool DRAFT=draft-2)
(. cwltool-venv/bin/activate && cd common-workflow-language && ./run_test.sh --junit-xml=result.xml RUNNER=cwltool DRAFT=draft-3)
(. cwltool-venv/bin/activate && cd common-workflow-language && ./run_test.sh --junit-xml=result.xml RUNNER=cwltool)
(. cwltool-venv/bin/activate && cd common-workflow-language && ./run_test.sh --junit-xml=result.xml RUNNER=cwltool DRAFT=v1.1.0-dev1 EXTRA=--enable-dev)
(. cwltool-venv/bin/activate && ./build-cwl-docker.sh && docker push commonworkflowlanguage/cwltool_module && docker push commonworkflowlanguage/cwltool)
