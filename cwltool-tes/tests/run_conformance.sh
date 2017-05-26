#!/bin/bash

BDIR="$(cd `dirname $0`; pwd)"

if [ -n "$1" ]; then
    TEST=-n$1
fi

pushd $BDIR/../../cwltool/schemas
./run_test.sh $TEST RUNNER=$BDIR/../cwltool-tes DRAFT=v1.0
## cleanup tmpdir from execution
rm -rf v1.0[0-9a-zA-Z_]*
popd
