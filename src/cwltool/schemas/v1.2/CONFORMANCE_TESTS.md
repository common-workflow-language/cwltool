# Common workflow language conformance test suite

The conformance tests are intended to test feature coverage of a CWL
implementation.  It uses the module cwltest from https://github.com/common-workflow-language/cwltest/.

## Usage

```
$ ./run_test.sh
--- Running conformance test draft-3 on cwl-runner ---
Test [49/49]
All tests passed
```


## Options

RUNNER=other-cwl-runner

The CWL implementation to be tested.

-nN

Run a single specific test number N.

EXTRA=--parallel

Extra options to pass to the CWL runner

For example, to run conformance test 15 against the "cwltool"
reference implementation with `--parallel`:

```
$ ./run_test.sh RUNNER=cwltool -n15 EXTRA=--parallel
Test [15/49]
All tests passed
```

## Notes

_NOTE_: For running on OSX systems, you'll need to install coreutils via brew. This will add to your
system some needed GNU-like tools like `greadlink`.

1. If you haven't already, install [brew](http://brew.sh/) package manager in your mac
2. Run `brew install coreutils`
