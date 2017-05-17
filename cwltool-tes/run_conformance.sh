#!/bin/bash

BDIR="$(cd `dirname $0`; pwd)"

if [ ! -e common-workflow-language ]; then
  git clone https://github.com/common-workflow-language/common-workflow-language.git
fi

if [ -n "$1" ]; then
    TEST=-n$1
fi

pushd common-workflow-language
./run_test.sh $TEST RUNNER=$BDIR/cwltool-tes DRAFT=v1.0
# ./run_test.sh $TEST RUNNER=/usr/local/bin/cwltool DRAFT=v1.0
rm -rf v1.0[0-9a-zA-Z_]*
popd
