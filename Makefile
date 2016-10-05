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

# make pep8 to check for basic Python code compliance
# make autopep8 to fix most pep8 errors
# make pylint to check Python code for enhanced compliance including naming
#  and documentation
# make coverage-report to check coverage of the python scripts by the tests

MODULE=cwltool

# `SHELL=bash` doesn't work for some, so don't use BASH-isms like
# `[[` conditional expressions.
PYSOURCES=$(wildcard ${MODULE}/**.py tests/*.py) setup.py
DEVPKGS=pep8 diff_cover autopep8 pylint coverage pep257 flake8
DEBDEVPKGS=pep8 python-autopep8 pylint python-coverage pep257 sloccount python-flake8
VERSION=1.0.$(shell date +%Y%m%d%H%M%S --date=`git log --first-parent \
	--max-count=1 --format=format:%cI`)
mkfile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

## all         : default task
all:
	./setup.py develop

## help        : print this help message and exit
help: Makefile
	@sed -n 's/^##//p' $<

## install-dep : install most of the development dependencies via pip
install-dep:
	pip install --upgrade $(DEVPKGS)

## install-deb-dep: install most of the dev dependencies via apt-get
install-deb-dep:
	sudo apt-get install $(DEBDEVPKGS)

## install     : install the ${MODULE} module and schema-salad-tool
install: FORCE
	./setup.py build install

## dist        : create a module package for distribution
dist: dist/${MODULE}-$(VERSION).tar.gz

dist/${MODULE}-$(VERSION).tar.gz: $(SOURCES)
	./setup.py sdist

## clean       : clean up all temporary / machine-generated files
clean: FORCE
	rm -f ${MODILE}/*.pyc tests/*.pyc
	./setup.py clean --all || true
	rm -Rf .coverage
	rm -f diff-cover.html

## pep8        : check Python code style
pep8: $(PYSOURCES)
	pep8 --exclude=_version.py  --show-source --show-pep8 $^ || true

pep8_report.txt: $(PYSOURCES)
	pep8 --exclude=_version.py $^ > pep8_report.txt || true

diff_pep8_report: pep8_report.txt
	diff-quality --violations=pep8 pep8_report.txt

## pep257      : check Python code style
pep257: $(PYSOURCES)
	pep257 --ignore=D100,D101,D102,D103 $^ || true

pep257_report.txt: $(PYSOURCES)
	pep257 setup.py $^ > pep257_report.txt 2>&1 || true

diff_pep257_report: pep257_report.txt
	diff-quality --violations=pep8 pep257_report.txt

## autopep8    : fix most Python code indentation and formatting
autopep8: $(PYSOURCES)
	autopep8 --recursive --in-place --ignore E309 $^

# A command to automatically run astyle and autopep8 on appropriate files
## format      : check/fix all code indentation and formatting (runs autopep8)
format: autopep8
	# Do nothing

## pylint      : run static code analysis on Python code
pylint: $(PYSOURCES)
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
                $^ || true

pylint_report.txt: ${PYSOURCES}
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
		$^ > pylint_report.txt || true

diff_pylint_report: pylint_report.txt
	diff-quality --violations=pylint pylint_report.txt

.coverage: $(PYSOURCES) all
	export COVERAGE_PROCESS_START=${mkfile_dir}.coveragerc; \
	       cd ${CWL}; ./run_test.sh RUNNER=cwltool
	coverage run setup.py test
	coverage combine ${CWL} ${CWL}/draft-3/ ./

coverage.xml: .coverage
	python-coverage xml

coverage.html: htmlcov/index.html

htmlcov/index.html: .coverage
	python-coverage html
	@echo Test coverage of the Python code is now in htmlcov/index.html

coverage-report: .coverage
	python-coverage report

diff-cover: coverage-gcovr.xml coverage.xml
	diff-cover coverage-gcovr.xml coverage.xml

diff-cover.html: coverage-gcovr.xml coverage.xml
	diff-cover coverage-gcovr.xml coverage.xml \
		--html-report diff-cover.html

## test        : run the ${MODULE} test suite
test: FORCE
	./setup.py test

sloccount.sc: ${PYSOURCES} Makefile
	sloccount --duplicates --wide --details $^ > sloccount.sc

## sloccount   : count lines of code
sloccount: ${PYSOURCES} Makefile
	sloccount $^

list-author-emails:
	@echo 'name, E-Mail Address'
	@git log --format='%aN,%aE' | sort -u | grep -v 'root'


mypy: ${PYSOURCES}
	rm -Rf typeshed/2.7/ruamel/yaml
	ln -s $(shell python -c 'from __future__ import print_function; import ruamel.yaml; import os.path; print(os.path.dirname(ruamel.yaml.__file__))') \
		typeshed/2.7/ruamel/yaml
	rm -Rf typeshed/2.7/schema_salad
	ln -s $(shell python -c 'from __future__ import print_function; import schema_salad; import os.path; print(os.path.dirname(schema_salad.__file__))') \
		typeshed/2.7/schema_salad
	MYPYPATH=typeshed/2.7 mypy --py2 --disallow-untyped-calls \
		 --warn-redundant-casts --warn-unused-ignores --fast-parser \
		 cwltool

FORCE:
