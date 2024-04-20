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

# Set these variables when running the script, e.g.:
# VERSION=v1.2 GIT_TARGET=main CONTAINER=podman ./conformance_test.sh

# Version of the standard to test against
# Current options: v1.0, v1.1, v1.2
VERSION=${VERSION:-"v1.2"}

# Which commit of the standard's repo to use
# Defaults to the last commit of the main branch
GIT_TARGET=${GIT_TARGET:-"main"}

# Which container runtime to use
# Valid options: docker, singularity
CONTAINER=${CONTAINER:-docker}

# Comma-separated list of test names that should be excluded from execution
# Defaults to "docker_entrypoint, inplace_update_on_file_content"
# EXCLUDE=${EXCLUDE:-"some_default_test_to_exclude"}

set -e
set -x

# Additional arguments for the pytest command
# Defaults to none
# PYTEST_EXTRA=

# The directory where this script resides
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

TMP_DIR=${TMP_DIR:-${SCRIPT_DIRECTORY}}

# Download archive from GitHub
if [[ "${VERSION}" = "v1.0" ]] ; then
    REPO=common-workflow-language
else
    # shellcheck disable=SC2001
    REPO=cwl-$(echo "$VERSION" | sed 's/\(v[0-9]*\.\)\([0-9]*\).*/\1\2/')
fi

if [ ! -d "${TMP_DIR}/${REPO}-${GIT_TARGET}" ] ; then
	if [ ! -f "${TMP_DIR}/${GIT_TARGET}.tar.gz" ] ; then
	  wget --directory-prefix "${TMP_DIR}" "https://github.com/common-workflow-language/${REPO}/archive/${GIT_TARGET}.tar.gz"
  fi
  tar --directory "${TMP_DIR}" -x -f "${TMP_DIR}/${GIT_TARGET}.tar.gz"
fi

if [ -v SKIP_PULL ] ; then
    echo Skipping node container pull.
elif [ "${CONTAINER}" == "docker" ]; then
    docker pull docker.io/node:slim
elif [ "${CONTAINER}" == "podman" ]; then
    podman pull docker.io/node:slim
elif [ "${CONTAINER}" == "singularity" ]; then
    export CWL_SINGULARITY_CACHE="$SCRIPT_DIRECTORY/sifcache"
    mkdir --parents "${CWL_SINGULARITY_CACHE}"
fi

# Setup environment
if [ -v SKIP_INSTALL ] ; then
   echo 'Skip installing dependencies; cwltool & cwltest must already be installed'
else
	venv "${TMP_DIR}/cwl-conformance-venv"
	pip install -U setuptools wheel pip
	pip uninstall -y cwltool
	pip install -r"${SCRIPT_DIRECTORY}/mypy-requirements.txt"
	CWLTOOL_USE_MYPYC=1 MYPYPATH="${SCRIPT_DIRECTORY}/mypy-stubs" pip install "${SCRIPT_DIRECTORY}" -r"${SCRIPT_DIRECTORY}/requirements.txt"
	pip install 'cwltest>=2.5' pytest-cov pytest-xdist>=3.2.0 psutil
fi

# Set conformance test filename
if [[ "${VERSION}" = "v1.0" ]] ; then
  CONFORMANCE_TEST="${TMP_DIR}/${REPO}-${GIT_TARGET}/${VERSION}/conformance_test_v1.0.yaml"
else
  CONFORMANCE_TEST="${TMP_DIR}/${REPO}-${GIT_TARGET}/conformance_tests.yaml"
fi
cp "${CONFORMANCE_TEST}" "${CONFORMANCE_TEST%".yaml"}.cwltest.yaml"
CONFORMANCE_TEST="${CONFORMANCE_TEST%".yaml"}.cwltest.yaml"

CWLTOOL_OPTIONS+=" --parallel"
unset exclusions
declare -a exclusions
if [[ "$VERSION" = *dev* ]]
then
    CWLTOOL_OPTIONS+=" --enable-dev"
fi
if [[ "$CONTAINER" = "singularity" ]]; then
    CWLTOOL_OPTIONS+=" --singularity"
    # This test fails because Singularity and Docker have
    # different views on how to deal with this.
    exclusions+=(docker_entrypoint)
    if [[ "${VERSION}" = "v1.1" ]]; then
        # This fails because of a difference (in Singularity vs Docker) in
        # the way filehandles are passed to processes in the container and
        # wc can tell somehow.
        # See issue #1440
        exclusions+=(stdin_shorcut)
    fi
elif [[ "$CONTAINER" = "podman" ]]; then
    CWLTOOL_OPTIONS+=" --podman"
fi

if [[ -n "${EXCLUDE}" ]] ; then
    EXCLUDE="${EXCLUDE},"
fi
if (( "${#exclusions[*]}" > 0 )); then
    EXCLUDE=${EXCLUDE}$(IFS=,; echo "${exclusions[*]}")
fi

# Build command
TEST_COMMAND="python -m pytest ${CONFORMANCE_TEST} -n logical --dist worksteal -rs --junit-xml=${TMP_DIR}/cwltool_conf_${VERSION}_${GIT_TARGET}_${CONTAINER}.xml -o junit_suite_name=cwltool_$(echo "${CWLTOOL_OPTIONS}" | tr "[:blank:]-" _)"
if [[ -n "${EXCLUDE}" ]] ; then
  TEST_COMMAND="${TEST_COMMAND} --cwl-exclude ${EXCLUDE}"
fi
if [ -v SKIP_COV ] ; then
	echo Skipping gathering of coverage information
else
	TEST_COMMAND="${TEST_COMMAND} --cov --cov-config ${SCRIPT_DIRECTORY}/.coveragerc --cov-report= ${PYTEST_EXTRA}"
	# Clean up all old coverage data
	find "${SCRIPT_DIRECTORY}" \( -type f -name .coverage -or -name '.coverage.*' -or -name coverage.xml \) -delete
fi


if [ "$GIT_BRANCH" = "origin/main" ] && [[ "$VERSION" = "v1.0" ]] && [[ "$CONTAINER" = "docker" ]]
then
    rm -Rf conformance
    # shellcheck disable=SC2154
    git clone http://"${jenkins_cwl_conformance}"@github.com/common-workflow-language/conformance.git

    git -C conformance config user.email "cwl-bot@users.noreply.github.com"
    git -C conformance config user.name "CWL Jenkins build bot"
    tool_ver=$(cwltool --version | awk '{ print $2 }')
    badgedir=${PWD}/conformance/cwltool/cwl_${VERSION}/cwltool_${tool_ver}
    mkdir -p "${PWD}"/conformance/cwltool/cwl_"${VERSION}"/
    rm -fr "${badgedir}"
    TEST_COMMAND="${TEST_COMMAND} --cwl-badgedir=${badgedir}"
    CONFORMANCE_MSG=$(cat << EOM
Conformance test of cwltool ${tool_ver} for CWL ${VERSION}
Commit: ${GIT_COMMIT}
Python version: 3
Container: ${CONTAINER}
Extra options: ${CWLTOOL_OPTIONS}
EOM
)
fi

export CWLTOOL_OPTIONS
echo CWLTOOL_OPTIONS="${CWLTOOL_OPTIONS}"

# Run test
cp "${SCRIPT_DIRECTORY}/tests/cwl-conformance/cwltool-conftest.py" "$(dirname "${CONFORMANCE_TEST}")/conftest.py"
bash -c "cd ${TMP_DIR} && ${TEST_COMMAND}"
RETURN_CODE=$?

# Coverage report
if [ ! -v SKIP_COV ] && [ "${RETURN_CODE}" -eq "0" ] ; then
  coverage report
  coverage xml
fi

if [ -d conformance ]
then
    rm -rf conformance/cwltool/cwl_"${VERSION}"/cwltool_latest
    cp -r conformance/cwltool/cwl_"${VERSION}"/cwltool_"${tool_ver}" conformance/cwltool/cwl_"${VERSION}"/cwltool_latest
    git -C conformance add --all
    git -C conformance diff-index --quiet HEAD || git -C conformance commit -m "${CONFORMANCE_MSG}"
    git -C conformance push http://"${jenkins_cwl_conformance}":x-oauth-basic@github.com/common-workflow-language/conformance.git
fi

# Cleanup
if [ -z "$SKIP_INSTALL" ] ; then
	echo Skipping venv cleanup
else
	deactivate
fi
#rm -rf "${GIT_TARGET}.tar.gz" "${SCRIPT_DIRECTORY}/${REPO}-${GIT_TARGET}" "${SCRIPT_DIRECTORY}/cwl-conformance-venv"

# Exit
exit ${RETURN_CODE}
