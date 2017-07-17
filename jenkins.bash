#!/usr/bin/bash
cloneorpull() {
        if test -d "$1" ; then
                (cd "$1" && git pull)
        else
                git clone "$2"
        fi
}
venv() {
        if ! test -d "$1" ; then
                virtualenv "$1"
        fi
	# shellcheck source=/dev/null
        source "$1"/bin/activate
}
cloneorpull common-workflow-language https://github.com/common-workflow-language/common-workflow-language.git
venv cwltool-venv
docker pull node:slim
export PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/
pip install -U setuptools wheel pip
python setup.py install
pip install "cwltest>=1.0.20160825151655"
pushd common-workflow-language
git clean --force -d -x || /bin/true
./run_test.sh --junit-xml=result.xml RUNNER=cwltool DRAFT=draft-3 && \
	./run_test.sh --junit-xml=result.xml RUNNER=cwltool && \
	./run_test.sh --junit-xml=result.xml RUNNER=cwltool DRAFT=v1.1.0-dev1 EXTRA=--enable-dev
CODE=$?
popd
if [ "$GIT_BRANCH" = "origin/master" ]
then
  ./build-cwl-docker.sh && docker push commonworkflowlanguage/cwltool_module && docker push commonworkflowlanguage/cwltool
fi
#docker rm -v $(docker ps -a -f status=exited | sed 's/  */ /g' | cut -d' ' -f1)
return ${CODE}
