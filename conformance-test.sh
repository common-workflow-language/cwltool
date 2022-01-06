#!/bin/bash
venv() {
    if ! test -d "$1" ; then
	if command -v virtualenv > /dev/null; then
            virtualenv -p python3 "$1"
	else
	    python3 -m venv "$1"
	fi
    fi
    # shellcheck source=/dev/null
    source "$1"/bin/activate
}

# Set these environment variables when running the script, e.g.:
# version=v1.1 spec_branch=new_test container=docker ./conformance_test.sh

# Version of the standard to test against
# Current options: v1.0, v1.1, v1.2
version=${version:-v1.0}

# Which branch of the standard's repo to use.
# This can be useful when adding new features
spec_branch=${spec_branch:-main}

# Which container runtime to use
# Valid options: docker, singularity
container=${container:-docker}

set -e
set -x

if [[ "$version" = "v1.0" ]] ; then
    repo=common-workflow-language
else
    # shellcheck disable=SC2001
    repo=cwl-$(echo "$version" | sed 's/\(v[0-9]*\.\)\([0-9]*\).*/\1\2/')
fi

if [ ! -d "${repo}-${spec_branch}" ]; then
    if [ ! -f "${repo}-${spec_branch}.tar.gz" ]; then
	wget "https://github.com/common-workflow-language/${repo}/archive/${spec_branch}.tar.gz"
    fi
    tar xzf "${spec_branch}.tar.gz"
fi

if [ "${container}" == "docker" ]; then
    docker pull docker.io/node:slim
fi

if [ "${container}" == "podman" ]; then
    podman pull docker.io/node:slim
fi

venv cwltool-venv3
pip3 install -U setuptools wheel pip
pip3 uninstall -y cwltool
pip3 install -e .
pip3 install codecov cwltest>=2.1
pushd "${repo}-${spec_branch}" || exit 1

# shellcheck disable=SC2043
if [[ "$version" = "v1.0" ]]; then
    DRAFT="DRAFT=v1.0"
fi
# Clean up all cov data
find . -name '.coverage*' -print0 | xargs -0 rm -f
rm -f coverage.xml

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
unset exclusions
declare -a exclusions

EXTRA="--parallel"
# shellcheck disable=SC2154
if [[ "$version" = *dev* ]]
then
    EXTRA+=" --enable-dev"
fi

if [[ "$container" = "singularity" ]]; then
    EXTRA+=" --singularity"
    # This test fails because Singularity and Docker have
    # different views on how to deal with this.
    exclusions+=(docker_entrypoint)

    if [[ "${version}" = "v1.1" ]]; then
        # This fails because of a difference (in Singularity vs Docker) in
        # the way filehandles are passed to processes in the container and
        # wc can tell somehow.
        # See issue #1440
        exclusions+=(stdin_shorcut)
    fi
elif [[ "$container" = "podman" ]]; then
    EXTRA+=" --podman"
fi

if [ -n "$EXTRA" ]
then
    EXTRA="EXTRA=${EXTRA}"
fi
if [ "$GIT_BRANCH" = "origin/main" ] && [[ "$version" = "v1.0" ]] && [[ "$container" = "docker" ]]
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
Container: ${container}
EOM
)

    tool_ver=$(cwltool --version | awk '{ print $2 }')
    badgedir=${PWD}/conformance/cwltool/cwl_${version}/cwltool_${tool_ver}
    mkdir -p "${PWD}"/conformance/cwltool/cwl_"${version}"/
    rm -fr "${badgedir}"
    BADGE=" --badgedir=${badgedir}"
fi

if (( "${#exclusions[*]}" > 0 )); then
    EXCLUDE=-S$(IFS=,; echo "${exclusions[*]}")
else
    EXCLUDE=""
fi
# shellcheck disable=SC2086
LC_ALL=C.UTF-8 ./run_test.sh --junit-xml=result3.xml ${EXCLUDE} \
      RUNNER=${CWLTOOL_WITH_COV} "-j$(nproc)" ${BADGE} \
      ${DRAFT} "${EXTRA}" \
      "--classname=py3_${container}"
# LC_ALL=C is to work around junit-xml ASCII only bug

# capture return code of ./run_test.sh
CODE=$?

find . -name '.coverage.*' -print0 | xargs -0 coverage combine --rcfile="${COVERAGE_RC}" --append
coverage xml --rcfile="${COVERAGE_RC}"
codecov --file coverage.xml

if [ -d conformance ]
then
    rm -rf conformance/cwltool/cwl_"${version}"/cwltool_latest
    cp -r conformance/cwltool/cwl_"${version}"/cwltool_"${tool_ver}" conformance/cwltool/cwl_"${version}"/cwltool_latest
    git -C conformance add --all
    git -C conformance diff-index --quiet HEAD || git -C conformance commit -m "${CONFORMANCE_MSG}"
    git -C conformance push http://"${jenkins_cwl_conformance}":x-oauth-basic@github.com/common-workflow-language/conformance.git
fi

popd || exit
deactivate

# build new docker container
# if [ "$GIT_BRANCH" = "origin/main" ] && [[ "$version" = "v1.0" ]]
# then
#   ./build-cwltool-docker.sh || true
# fi
#docker rm -v $(docker ps -a -f status=exited | sed 's/  */ /g' | cut -d' ' -f1)
exit ${CODE}
