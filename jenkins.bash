#!/bin/bash
if [[ -z "${JENKINS_URL}" ]]
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
                virtualenv -p python"${PYTHON_VERSION}" "$1"
        fi
	# shellcheck source=/dev/null
        source "$1"/bin/activate
}

cloneorpull common-workflow-language https://github.com/common-workflow-language/common-workflow-language.git
docker pull node:slim
# clean both the repos before the loop
git clean --force -d -x || /bin/true
git -C common-workflow-language clean --force -d -x || /bin/true

# Test for Python 2.7 and Python 3
for PYTHON_VERSION in 2 3
do
for CONTAINER in docker
# for CONTAINER in docker singularity
# singularity having issues on ci.commonwl.org; tests pass with https://gist.github.com/mr-c/0ec90d717617d074017c0cb38b72d1a4
do
	venv cwltool-venv${PYTHON_VERSION}
	export PIP_DOWNLOAD_CACHE=/var/lib/jenkins/pypi-cache/
	# use pip2.7 and pip3 in separate loop runs
	pip${PYTHON_VERSION} install -U setuptools wheel pip
	pip${PYTHON_VERSION} uninstall -y cwltool
	pip${PYTHON_VERSION} install .
	pip${PYTHON_VERSION} install -U "cwltest>=1.0.20180130081614"
	pushd common-workflow-language
	# shellcheck disable=SC2154
	if [[ "$version" = *dev* ]]
	then
		EXTRA=" --enable-dev"
	else
		EXTRA=""
	fi
	if [[ "$CONTAINER" = "singularity" ]]
	then
		EXTRA+=" --singularity"
	fi
	if [ -n "$EXTRA" ]
	then
		EXTRA="EXTRA=${EXTRA}"
	fi
	# shellcheck disable=SC2086
	LC_ALL=C ./run_test.sh --junit-xml=result${PYTHON_VERSION}.xml RUNNER=cwltool \
		-j4 DRAFT="${version}" "${EXTRA}" \
		"--classname=py${PYTHON_VERSION}_${CONTAINER}"
	# LC_ALL=C is to work around junit-xml ASCII only bug
	CODE=$((CODE+$?)) # capture return code of ./run_test.sh
	deactivate
	popd
done
done

# build new docker container
if [ "$GIT_BRANCH" = "origin/master" ] && [[ "$version" = "v1.0" ]]
then
  ./build-cwl-docker.sh && docker push commonworkflowlanguage/cwltool_module && docker push commonworkflowlanguage/cwltool
fi
#docker rm -v $(docker ps -a -f status=exited | sed 's/  */ /g' | cut -d' ' -f1)
exit ${CODE}
