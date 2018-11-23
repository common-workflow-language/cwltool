#!/bin/bash

set -e
set -x

export LC_ALL=C

package=cwltool
module=cwltool
slug=${TRAVIS_PULL_REQUEST_SLUG:=common-workflow-language/cwltool}
repo=https://github.com/${slug}.git
run_tests_installed_package() {
	local mod_loc
	mod_loc=$(pip show ${package} |
		grep ^Location | awk '{print $2}')/${module}
	pytest "--ignore=${mod_loc}/schemas/" \
		--pyargs -x ${module} -n auto --dist=loadfile
}
pipver=10.0.0 # required to install build deps

rm -Rf testenv? || /bin/true

export HEAD=${TRAVIS_PULL_REQUEST_SHA:-$(git rev-parse HEAD)}

if [ "${RELEASE_SKIP}" != "head" ]
then
	virtualenv testenv1
	virtualenv testenv0
	# First we test the head
	# shellcheck source=/dev/null
	source testenv1/bin/activate
	rm -Rf testenv1/{local,lib/python-wheels/setuptools*}
	pip install --force-reinstall -U pip\>=${pipver}
	pip install .[test,deps]
	make test
	pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
	mkdir testenv1/not-${module}
	# Avoid having a subdir named '${module}' pytest may execute tests from that dir
	# instead of the installed module's tests
	pushd testenv1/not-${module}
	# shellcheck disable=SC2086
	run_tests_installed_package
	deactivate; popd
fi

virtualenv testenv2
virtualenv testenv3
virtualenv testenv4
rm -Rf testenv[234]/local

# Install the package using git, run the tests in-place
# Create a package to later run tests on those

# shellcheck source=/dev/null
source testenv2/bin/activate
rm -Rf testenv2/{local,src,lib/python-wheels/setuptools*}
pushd testenv2
pip install --force-reinstall -U pip\>=${pipver}
pip install -e "git+${repo}@${HEAD}#egg=${package}[test,deps]"
pushd src/${package}
make test
make dist
pushd dist
package_tar=(${package}*.tar.gz)
popd
cp dist/${package_tar} ../../../testenv3/
deactivate; popd; popd

# Is the distribution in testenv2 complete enough to build another
# functional distribution?

# shellcheck source=/dev/null
source testenv3/bin/activate
rm -Rf testenv3/{local,lib/python-wheels/setuptools*}
pushd testenv3/
pip install --force-reinstall -U pip\>=${pipver}
pip install "${package_tar}""[test,deps]"
mkdir out
tar --extract --directory=out -z -f "${package_tar}"
pushd out/${package}*
make install-dep
make test
# Avoid having a subdir named '${module}' pytest may execute tests from that dir
# instead of the installed module's tests
popd; rm -Rf out/
# shellcheck disable=SC2086
run_tests_installed_package
deactivate; popd

# Install the package using git, run the tests from the package

# shellcheck source=/dev/null
source testenv4/bin/activate
rm -Rf testenv4/{local,lib/python-wheels/setuptools*}
pushd testenv4
pip install "git+${repo}@${HEAD}#egg=${package}""[test,deps]"
# no subdir named ${proj} here, safe for testing the installed module
# shellcheck disable=SC2086
run_tests_installed_package
deactivate; popd;
