#!/bin/bash

set -e
set -x

export LC_ALL=C

package=cwltool
module=cwltool
slug=${TRAVIS_PULL_REQUEST_SLUG:=common-workflow-language/cwltool}
repo=https://github.com/${slug}.git
run_tests="bin/py.test --ignore ${module}/schemas/ --pyarg -x cwltool -n$(nproc) --dist=loadfile"
pipver=7.0.2 # minimum required version of pip
setuptoolsver=24.2.0 # required to generate correct metadata for
                     # python_requires
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

rm -Rf testenv? || /bin/true

export HEAD=${TRAVIS_PULL_REQUEST_SHA:-$(git rev-parse HEAD)}

if [ "${RELEASE_SKIP}" != "head" ]
then
	virtualenv testenv1
	# First we test the head
	# shellcheck source=/dev/null
	source testenv1/bin/activate
	rm testenv1/lib/python-wheels/setuptools* \
		&& pip install --force-reinstall -U pip==${pipver} \
	        && pip install setuptools==${setuptoolsver} wheel
	make install-dep
	#pip install 'galaxy-lib>=17.09.3'
	make test
	pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
	mkdir testenv1/not-${module}
	# if there is a subdir named '${module}' py.test will execute tests
	# there instead of the installed module's tests
	pushd testenv1/not-${module}
	# shellcheck disable=SC2086
	../${run_tests}; popd
fi

virtualenv testenv2
virtualenv testenv3
virtualenv testenv4


# Secondly we test via pip

cd testenv2
# shellcheck source=/dev/null
source bin/activate
rm lib/python-wheels/setuptools* \
	&& pip install --force-reinstall -U pip==${pipver} \
        && pip install setuptools==${setuptoolsver} wheel
#pip install 'galaxy-lib==17.09.3'
pip install -e "git+${repo}@${HEAD}#egg=${package}"  #[deps]
cd src/${package}
make install-dep
make dist
make test
cp dist/${package}*tar.gz ../../../testenv3/
pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
cd ../.. # no subdir named ${proj} here, safe for py.testing the installed module
# shellcheck disable=SC2086
${run_tests}

# Is the distribution in testenv2 complete enough to build another
# functional distribution?

cd ../testenv3/
# shellcheck source=/dev/null
source bin/activate
rm lib/python-wheels/setuptools* \
	&& pip install --force-reinstall -U pip==${pipver} \
        && pip install setuptools==${setuptoolsver} wheel
package_tar=${package}*tar.gz
pip install "-r${DIR}/test-requirements.txt"
#pip install 'galaxy-lib==17.09.3'
pip install ${package_tar}  # [deps]
mkdir out
tar --extract --directory=out -z -f ${package}*.tar.gz
cd out/${package}*
make install-dep
make dist
make test
pip uninstall -y ${package} || true; pip uninstall -y ${package} || true; make install
mkdir ../not-${module}
pushd ../not-${module}
# shellcheck disable=SC2086
../../${run_tests}; popd
