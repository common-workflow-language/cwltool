#!/bin/bash
venv() {
        if ! test -d "$1" ; then
                virtualenv -p python3 "$1"
        fi
	# shellcheck source=/dev/null
        source "$1"/bin/activate
}
version=${version:-v1.0}
if [[ "$version" = "v1.0" ]] ; then
   wget https://github.com/common-workflow-language/common-workflow-language/archive/main.tar.gz
   tar xzf main.tar.gz && rm main.tar.gz
else
    # shellcheck disable=SC2001
    repo=$(echo "$version" | sed 's/\(v[0-9]*\.\)\([0-9]*\).*/\1\2/')  
    wget https://github.com/common-workflow-language/cwl-"${repo}"/archive/main.tar.gz
    tar xzf main.tar.gz && rm main.tar.gz
fi

docker pull node:slim

# shellcheck disable=SC2043
for CONTAINER in docker
# for CONTAINER in docker singularity
# singularity having issues on ci.commonwl.org; tests pass with https://gist.github.com/mr-c/0ec90d717617d074017c0cb38b72d1a4
do
	venv cwltool-venv3
	pip3 install -U setuptools wheel pip
	pip3 uninstall -y cwltool
	pip3 install -e .
	pip3 install "cwltest>=1.0.20180518074130" codecov
	if [[ "$version" = "v1.0" ]]
	then
		DRAFT="DRAFT=v1.0"
		pushd common-workflow-language-main || exit 1
	else
		pushd cwl-"${repo}"-main || exit 1
	fi
	rm -f .coverage* coverage.xml
	source=$(realpath ../cwltool)
	COVERAGE_RC=${PWD}/.coveragerc
	cat > "${COVERAGE_RC}" <<EOF
[run]
branch = True
source = ${source}

[report]
exclude_lines =
    if self.debug:
    pragma: no cover
    raise NotImplementedError
    if __name__ == .__main__.:
ignore_errors = True
omit =
    tests/*
EOF
	CWLTOOL_WITH_COV=${PWD}/cwltool_with_cov3
	cat > "${CWLTOOL_WITH_COV}" <<EOF
#!/bin/bash
coverage run --parallel-mode --rcfile=${COVERAGE_RC} \
	"$(command -v cwltool)" "\$@"
EOF
	chmod a+x "${CWLTOOL_WITH_COV}"
	EXTRA="--parallel"
	# shellcheck disable=SC2154
	if [[ "$version" = *dev* ]]
	then
		EXTRA+=" --enable-dev"
	fi
	if [[ "$CONTAINER" = "singularity" ]]
	then
		EXTRA+=" --singularity"
	fi
	if [ -n "$EXTRA" ]
	then
		EXTRA="EXTRA=${EXTRA}"
	fi
	if [ "$GIT_BRANCH" = "origin/main" ] && [[ "$version" = "v1.0" ]] && [[ "$CONTAINER" = "docker" ]]
	then
		rm -Rf conformance
                # shellcheck disable=SC2154
		git clone http://"${jenkins_cwl_conformance}"@github.com/common-workflow-language/conformance.git

		git -C conformance config user.email "cwl-bot@users.noreply.github.com"
		git -C conformance config user.name "CWL Jenkins build bot"
		CONFORMANCE_MSG=$(cat << EOM
Conformance test of cwltool ${tool_ver} for CWL ${version}
Commit: ${GIT_COMMIT}
Python version: 3
Container: ${CONTAINER}
EOM
)

		tool_ver=$(cwltool --version | awk '{ print $2 }')
		badgedir=${PWD}/conformance/cwltool/cwl_${version}/cwltool_${tool_ver}
		mkdir -p "${PWD}"/conformance/cwltool/cwl_"${version}"/
		rm -fr "${badgedir}"
		BADGE=" --badgedir=${badgedir}"
	fi
	# shellcheck disable=SC2086
	LC_ALL=C.UTF-8 ./run_test.sh --junit-xml=result3.xml \
		RUNNER=${CWLTOOL_WITH_COV} "-j$(nproc)" ${BADGE} \
		${DRAFT} "${EXTRA}" \
		"--classname=py3_${CONTAINER}"
	# LC_ALL=C is to work around junit-xml ASCII only bug
	CODE=$((CODE+$?)) # capture return code of ./run_test.sh
	coverage combine "--rcfile=${COVERAGE_RC}" "$(find . -name '.coverage.*')"
	coverage xml "--rcfile=${COVERAGE_RC}"
	codecov --file coverage.xml

	if [ -d conformance ]
	then
		rm -rf conformance/cwltool/cwl_"${version}"/cwltool_latest
		cp -r conformance/cwltool/cwl_"${version}"/cwltool_"${tool_ver}" conformance/cwltool/cwl_"${version}"/cwltool_latest
		git -C conformance add --all
		git -C conformance diff-index --quiet HEAD || git -C conformance commit -m "${CONFORMANCE_MSG}"
		git -C conformance push http://"${jenkins_cwl_conformance}":x-oauth-basic@github.com/common-workflow-language/conformance.git
	fi

	deactivate
	popd || exit
done
# build new docker container
if [ "$GIT_BRANCH" = "origin/main" ] && [[ "$version" = "v1.0" ]]
then
  ./build-cwl-docker.sh || true
fi
#docker rm -v $(docker ps -a -f status=exited | sed 's/  */ /g' | cut -d' ' -f1)
exit ${CODE}
