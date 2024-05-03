#!/bin/bash

set -e
set -x

export LC_ALL=C

package=cwltool
module=cwltool
extras="[deps]"

if [ "$GITHUB_ACTIONS" = "true" ]; then
    # We are running as a GH Action
    repo=${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}.git
    HEAD=${GITHUB_REF}
else
    repo=https://github.com/common-workflow-language/cwltool.git
    HEAD=$(git rev-parse HEAD)
fi
test_prefix=""
run_tests() {
	local mod_loc
	mod_loc=$(pip show ${package} |
		grep ^Location | awk '{print $2}')/${module}
	"${test_prefix}"bin/py.test "--ignore=${mod_loc}/schemas/" \
		--pyargs -x ${module} -n logical --dist=worksteal
}
pipver=23.1  # minimum required version of pip for Python 3.12
setuptoolsver=67.6.1  # required for Python 3.12
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

rm -Rf testenv? || /bin/true


if [ "${RELEASE_SKIP}" != "head" ]
then
	python3 -m venv testenv1
	# First we test the head
	# shellcheck source=/dev/null
	source testenv1/bin/activate
	rm -Rf testenv1/local
	rm -f testenv1/lib/python-wheels/setuptools* \
		&& pip install --force-reinstall -U pip==${pipver} \
		&& pip install setuptools==${setuptoolsver} wheel
	pip install -rtest-requirements.txt ".${extras}"
	#make test
	pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
	# mkdir testenv1/not-${module}
	# if there is a subdir named '${module}' py.test will execute tests
	# there instead of the installed module's tests
	# pushd testenv1/not-${module}
	# #shellcheck disable=SC2086
	# test_prefix=../ run_tests; popd
fi

python3 -m venv testenv2
python3 -m venv testenv3
rm -Rf testenv[23]/local

# Secondly we test via pip

pushd testenv2
# shellcheck source=/dev/null
source bin/activate
rm -f lib/python-wheels/setuptools* \
	&& pip install --force-reinstall -U pip==${pipver} \
        && pip install setuptools==${setuptoolsver} wheel
# The following can fail if you haven't pushed your commits to ${repo}
pip install -e "git+${repo}@${HEAD}#egg=${package}${extras}"
pushd src/${package}
pip install -rtest-requirements.txt build
make dist
#make test
cp dist/${module}*tar.gz ../../../testenv3/
pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
popd # ../.. no subdir named ${proj} here, safe for py.testing the installed module
# shellcheck disable=SC2086
#run_tests
popd

# Is the source distribution in testenv2 complete enough to build another
# functional distribution?

pushd testenv3/
# shellcheck source=/dev/null
source bin/activate
rm -f lib/python-wheels/setuptools* \
	&& pip install --force-reinstall -U pip==${pipver} \
        && pip install setuptools==${setuptoolsver} wheel
package_tar=$(find . -name "${module}*tar.gz")
pip install "-r${DIR}/test-requirements.txt" udocker build
pip install "${package_tar}${extras}"
udocker install
mkdir out
tar --extract --directory=out -z -f ${module}*.tar.gz
pushd out/${module}*
make dist
make test
pip install "-r${DIR}/mypy-requirements.txt"
make mypyc
pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
mkdir ../not-${module}
pushd ../not-${module}
# shellcheck disable=SC2086
test_prefix=../../ run_tests; popd
popd
popd
