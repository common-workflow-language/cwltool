#!/bin/bash
if [ "$JENKINS_URL" == ""]
then
	echo "Looks like we're not being run by Jenkins, this is dangerous"
	echo "due to use of git clean -fdx command."
	exit 1
fi
cloneorpull() {
        if test -d "$1" ; then
                (cd "$1" && git pull)
        else
                git clone "$2"
        fi
}
venv() {
        if ! test -d "$1" ; then
                virtualenv -p python${PYTHON_VERSION} "$1"
        fi
	# shellcheck source=/dev/null
        source "$1"/bin/activate
}

git clean --force -d -x || /bin/true
cloneorpull common-workflow-language https://github.com/common-workflow-language/common-workflow-language.git
docker pull node:slim

# Test for Python 2.7 and Python 3
for PYTHON_VERSION in 2.7 3
do
	venv cwltool-venv${PYTHON_VERSION}
	export PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/
	# use pip2.7 and pip3 in separate loop runs
	pip${PYTHON_VERSION} install -U setuptools wheel pip
	pip${PYTHON_VERSION} install .
	pip${PYTHON_VERSION} install "cwltest>=1.0.20160825151655"
	pushd common-workflow-language
	git clean --force -d -x || /bin/true
	# shellcheck disable=SC2154
	if [[ "$version" = *dev* ]]
	then
		EXTRA="EXTRA=--enable-dev"
	fi
	./run_test.sh --junit-xml=result.xml RUNNER=cwltool -j4 DRAFT=${version}
	deactivate
	CODE=$?
	popd
done

# build new docker container
if [ "$GIT_BRANCH" = "origin/master" ] && [[ "$version" = "v1.0" ]]
then
  ./build-cwl-docker.sh && docker push commonworkflowlanguage/cwltool_module && docker push commonworkflowlanguage/cwltool
fi
#docker rm -v $(docker ps -a -f status=exited | sed 's/  */ /g' | cut -d' ' -f1)
exit ${CODE}
