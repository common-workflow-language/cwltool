# This file is part of cwltool,
# https://github.com/common-workflow-language/cwltool/, and is
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contact: common-workflow-language@googlegroups.com

# make format to fix most python formatting errors
# make pylint to check Python code for enhanced compliance including naming
#  and documentation
# make coverage-report to check coverage of the python scripts by the tests

MODULE=cwltool

# `SHELL=bash` doesn't work for some, so don't use BASH-isms like
# `[[` conditional expressions.
PYSOURCES=$(wildcard ${MODULE}/**.py tests/*.py) setup.py
DEVPKGS=diff_cover black pylint coverage pep257 pydocstyle flake8 mypy\
	pytest-xdist isort wheel autoflake -rtest-requirements.txt
DEBDEVPKGS=pep8 python-autopep8 pylint python-coverage pydocstyle sloccount \
	   python-flake8 python-mock shellcheck
VERSION=3.0.$(shell TZ=UTC git log --first-parent --max-count=1 \
	--format=format:%cd --date=format-local:%Y%m%d%H%M%S)
mkfile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
UNAME_S=$(shell uname -s)

## all         : default task
all:
	pip install -e .

## help        : print this help message and exit
help: Makefile
	@sed -n 's/^##//p' $<

## install-dep : install most of the development dependencies via pip
install-dep: install-dependencies

install-dependencies:
	pip install --upgrade $(DEVPKGS)
	pip install -r requirements.txt

## install-deb-dep: install most of the dev dependencies via apt-get
install-deb-dep:
	sudo apt-get install $(DEBDEVPKGS)

## install     : install the ${MODULE} module and schema-salad-tool
install: FORCE
	pip install .[deps]

## dev     : install the ${MODULE} module in dev mode
dev: install-dep
	pip install -e .[deps]


## dist        : create a module package for distribution
dist: dist/${MODULE}-$(VERSION).tar.gz

dist/${MODULE}-$(VERSION).tar.gz: $(SOURCES)
	./setup.py sdist bdist_wheel

## docs	       : make the docs
docs: FORCE
	cd docs && $(MAKE) html

## clean       : clean up all temporary / machine-generated files
clean: FORCE
	rm -f ${MODILE}/*.pyc tests/*.pyc
	./setup.py clean --all || true
	rm -Rf .coverage
	rm -f diff-cover.html

# Linting and code style related targets
## sorting imports using isort: https://github.com/timothycrosley/isort
sort_imports:
	isort ${MODULE}/*.py tests/*.py setup.py

remove_unused_imports: $(PYSOURCES)
	autoflake --in-place --remove-all-unused-imports $^

pep257: pydocstyle
## pydocstyle      : check Python code style
pydocstyle: $(PYSOURCES)
	pydocstyle --add-ignore=D100,D101,D102,D103 $^ || true

pydocstyle_report.txt: $(filter-out tests/%,${PYSOURCES})
	pydocstyle setup.py $^ > $@ 2>&1 || true

diff_pydocstyle_report: pydocstyle_report.txt
	diff-quality --compare-branch=main --violations=pydocstyle --fail-under=100 $^

## format      : check/fix all code indentation and formatting (runs black)
format:
	black --exclude cwltool/schemas setup.py cwltool.py cwltool tests

## pylint      : run static code analysis on Python code
pylint: $(PYSOURCES)
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
                $^ -j0|| true

pylint_report.txt: ${PYSOURCES}
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
		$^ -j0> $@ || true

diff_pylint_report: pylint_report.txt
	diff-quality --violations=pylint pylint_report.txt

.coverage: testcov

coverage: .coverage
	coverage report

coverage.xml: .coverage
	coverage xml

coverage.html: htmlcov/index.html

htmlcov/index.html: .coverage
	coverage html
	@echo Test coverage of the Python code is now in htmlcov/index.html

coverage-report: .coverage
	coverage report

diff-cover: coverage.xml
	diff-cover $^

diff-cover.html: coverage.xml
	diff-cover $^ --html-report $@

## test        : run the ${MODULE} test suite
test: $(pysources)
	python setup.py test --addopts "-n auto --dist=loadfile"

## testcov     : run the ${MODULE} test suite and collect coverage
testcov: $(pysources)
	python setup.py test --addopts "--cov cwltool -n auto --dist=loadfile"

sloccount.sc: ${PYSOURCES} Makefile
	sloccount --duplicates --wide --details $^ > $@

## sloccount   : count lines of code
sloccount: ${PYSOURCES} Makefile
	sloccount $^

list-author-emails:
	@echo 'name, E-Mail Address'
	@git log --format='%aN,%aE' | sort -u | grep -v 'root'

mypy3: mypy
mypy: $(filter-out setup.py gittagger.py,${PYSOURCES})
	if ! test -f $(shell python3 -c 'import ruamel.yaml; import os.path; print(os.path.dirname(ruamel.yaml.__file__))')/py.typed ; \
	then \
		rm -Rf typeshed/2and3/ruamel/yaml ; \
		ln -s $(shell python3 -c 'import ruamel.yaml; import os.path; print(os.path.dirname(ruamel.yaml.__file__))') \
			typeshed/2and3/ruamel/ ; \
	fi  # if minimally required ruamel.yaml version is 0.15.99 or greater, than the above can be removed
	MYPYPATH=$$MYPYPATH:typeshed/3:typeshed/2and3 mypy --disallow-untyped-calls \
		 --warn-redundant-casts \
		 $^

mypyc: ${PYSOURCES}
	MYPYPATH=typeshed/2and3/:typeshed/3 CWLTOOL_USE_MYPYC=1 pip install --verbose -e . && pytest --ignore cwltool/schemas --basetemp ./tmp

shellcheck: FORCE
	shellcheck build-cwl-docker.sh cwl-docker.sh release-test.sh travis.bash \
		cwltool-in-docker.sh

release-test: FORCE
	git diff-index --quiet HEAD -- || ( echo You have uncommited changes, please commit them and try again; false )
	./release-test.sh

release: release-test
	. testenv2/bin/activate && \
		testenv2/src/${MODULE}/setup.py sdist bdist_wheel && \
		pip install twine && \
		twine upload testenv2/src/${MODULE}/dist/* && \
		git tag ${VERSION} && git push --tags

FORCE:

# Use this to print the value of a Makefile variable
# Example `make print-VERSION`
# From https://www.cmcrossroads.com/article/printing-value-makefile-variable
print-%  : ; @echo $* = $($*)
