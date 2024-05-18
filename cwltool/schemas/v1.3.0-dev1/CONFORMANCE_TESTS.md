# Common workflow language conformance test suite

The conformance tests are intended to test feature coverage of a CWL
implementation.  It uses the module cwltest from https://github.com/common-workflow-language/cwltest/.

## Pre-requisites

You will need both the `cwltest` Python package  and the CWL runner you would like to test installed.

Installing the `cwltest` Python package using a virtualenv:

```
$ python3 -m venv cwltest_env
$ source cwltest_env/bin/activate
$ pip install cwltest
```

or via `bioconda`

```
$ conda install -c bioconda cwltest
```

## Usage

```bash
$ ./run_test.sh
--- Running conformance test draft-3 on cwl-runner ---
Test [49/49]
All tests passed
```


## Options

`RUNNER=other-cwl-runner`

The CWL implementation to be tested.

### Test Selection

`--tags`

A comma separated list of [tags](#tags-for-conformance-tests); only tests with these tags will be tested.
`--tags shell_command` will run all tests with `shell_command` in their `tags` list.

`-n{test_range}`

Run only the specific test numbers. `{test_range}` is a comma separated list of
single test numbers and/or numeric ranges.
`-n5-7,15` == only runs the 5th, 6th, 7th, and 15th tests.

`-N{test_range}`

Like the lowercase `-n` option, except that the specified tests will not be run.
Can be mixed with the other test selectors: `-n5-7,15 -N6` == only runs the 5th, 7th, and 15th tests, skipping the 6th test.

`-s{test_names}`

Run the specific tests according to their `id`s. `{test_names}` is a comma separated list of
test identifiers (the `id` field). `-scl_optional_bindings_provided,stdout_redirect_docker,expression_any_null`
achieves the same effect as `-n5-7,15 -N6` and it will still work if the tests are re-ordered.

`-S{test_names}`

Excludes specific tests according to their `id`s. `{test_names}` is a comma separated list of
test identifiers (the `id` field). `--tags shell_command -Sstderr_redirect_shortcut`
will run all tests with `expression_tool` in their `tags` list except the test
with the `id` of `stderr_redirect_shortcut`.

### Misc

`EXTRA="--parallel --singularity"`

Extra options to pass to the CWL runner (check your runner for exact options)

`-j=4`

The number of different tests to run at the same time

`--junit-xml=FILENAME`

Store results in JUnit XML format using the given FILENAME.

`--classname=CLASSNAME`

In the JUnit XML, tag the results with the given CLASSNAME.
Can be useful when multiple test runs are combined to document the differences in `EXTRA=`.

---

For example, to run conformance test 15,16,17, and 20 against the "cwltool"
reference implementation using the `podman` container engine
and parallel execution of workflow steps

```bash
$ ./run_test.sh RUNNER=cwltool -n15-17,20 EXTRA="--parallel --podman"
Test [15/49]
Test [16/49]
Test [17/49]
Test [20/49]
All tests passed
```

## OS X / macOS Notes

_NOTE_: For running on OSX systems, you'll need to install coreutils via brew. This will add to your
system some needed GNU-like tools like `greadlink`.

1. If you haven't already, install [brew](http://brew.sh/) package manager in your mac
2. Run `brew install coreutils`

## Format of the conformance test file

A single conformance test consist of the path to an input CWL document plus an input CWL object
and the expected outputs (or `should_fail: true` if the test is deliberately broken)

They are stored in [`conformance_tests.yaml`](https://github.com/common-workflow-language/cwl-v1.2/blob/main/conformance_tests.yaml)
(or a file `$import`ed into that one)

You can examine [the formal schema of this file](https://github.com/common-workflow-language/cwltest/blob/main/cwltest/cwltest-schema.yml),
or just continue reading here for an explanation.

The conformance test file is a YAML document: a list of key-value pairs.

We will use this single entry to explain the format
``` yaml
- doc: Test command line with optional input (missing)
   id: cl_optional_inputs_missing
   tool: tests/cat1-testcli.cwl  
   job: tests/cat-job.json
   output:
     args: [cat, hello.txt]
   tags: [ required, command_line_tool ]
```
- `doc`: A unique, single-line sentence that explain what is being tested.
     Will be printed at test execution time, so please don't make it too long!
     Additional documentation can go as comments in the CWL document itself.
- `id`: a short list of  underscore (`_`) separated words that succinctly identifies and explains the test.
- `tool` the path to the CWL document to run
- `job`: the CWL input object in YAML/JSON format. If there are no inputs then use `tests/empty.json`.
- `output` [the CWL output object expected.](#output-matching)
- `tags`: a yaml list of tag names, see [the list of canonical tags below](#tags-for-conformance-tests).
     Must include one or more of the following tags: `command_line_tool`, `expression_tool` or `workflow`.
     If the test does not test any optional features, the tag `required` is required.

Because `conformance_tests.yaml` is a `schema-salad` processed document, [`$import`](https://www.commonwl.org/v1.3/SchemaSalad.html#Import)
can be used to organize the tests into separate files.

Currently, the main file is too big (over 3400 lines); we are slowly re-organizing it.

Eventually it would be good to organize the tests so that the test for each optional feature and other logical groups of tests are in their own separate file;
with the supporting CWL documents and their inputs in separate sub-folders of `tests` as well.

Example: [`- $import: tests/string-interpolation/test-index.yaml`](https://github.com/common-workflow-language/cwl-v1.2/blob/5f27e234b4ca88ed1280dedf9e3391a01de12912/conformance_tests.yaml#L3395)
adds all the entries in [`tests/string-interpolation/test-index.yaml`](https://github.com/common-workflow-language/cwl-v1.2/blob/main/tests/string-interpolation/test-index.yaml)
as entries in the main conformance test file.

## Output matching

In each test entry there is an `output` field that contains a mapping of the expected outputs names and their values.

If a particular value could vary and it doesn't matter to the proper functioning of the test, then it can be represented by the special token `Any`.

At any level, if there is an extra field, then that will be considered an error.
An exception to this is `class: File` and `class: Directory` objects, the `cwl-runner` under test can add additional fields here without causing a test to fail.
Likewise, if you don't want to test some aspect of a `class: File` or `class: Directory` object (like `nameext`) you can just omit it.

[According to the CWL standards](https://www.commonwl.org/v1.3/CommandLineTool.html#File), the format of the `location` field in 
`class: File` and `class: Directory` is implementation specific and we should not be testing them.
Please remember to use `location: Any` for them.

Currently, we do [test the contents of the location field in some older tests, but we should stop](https://github.com/common-workflow-language/common-workflow-language/issues/930)
If you are editing those old tests, you may be interested in some special processing for  `class: File` and `class: Directory` output objects:
any `location` value specified will succeed if there is either an exact match to the real output, or it matches the end of the real output.
Additionally, for `class: Directory` the location reported by the actual execution will have any trailing forward slash (`/`) trimmed off before comparison.

Likewise, please do not test the `path` for `class: File` and `class: Directory`.

## Writing a new conformance test

To add a new conformance test:
1. Ensure the CWL document you have tests the desired feature or aspect.
2. The `cwlVersion` should be the latest version (`cwlVersion: v1.2`), unless
   testing the mixing of versions as in the `tests/mixed-versions` directory.
3. All `CommandLineTool`s need a software container (via `DockerRequirement`) for better reproducibility, preferably under `hints`.
     Please limit your container usage to the following: 
     - `dockerPull: docker.io/alpine:latest`
     - `dockerPull: docker.io/bash:4.4`
     - `dockerPull: docker.io/debian:stable-slim`
     - `dockerPull: docker.io/python:3-slim`
4. Run your test using the CWL reference runner (`cwltool`) or another CWL runner
     that shows the correct behavior to collect the output, or confirm that validation/execution fails as expected
5. Add the CWL document and output object to the subdirectory `tests` in this repository.
6. Fill out a new entry in [conformance_tests.yaml](conformance_tests.yaml) following the [format of the conformance test file](#format-of-the-conformance-test-file)
7. Send a pull request to [current staging branch for the next revision of the CWL standards](https://github.com/common-workflow-language/cwl-v1.2/tree/1.2.1_proposed) 
     with your changes

## Tags for conformance tests

Each test in the [conformance_tests.yaml](conformance_tests.yaml) should be tagged with one or more tags.

1. A `command_line_tool`, `expression_tool` or `workflow` tag to identify whether a CommandLineTool, ExpressionTool
   or Workflow is being tested
2. If the test does not test any optional features, the tag `required`
3. The name of any features that are being tested:
    1. `docker` for DockerRequirement
    1. `env_var` for EnvVarRequirement
    1. `format_checking` for checking format requirement annotation on File inputs
    1. `initial_work_dir` for InitialWorkDirRequirements
    1. `inline_javascript` for InlineJavascriptRequirement
    1. `inplace_update` for InplaceUpdateRequirement
    1. `input_object_requirements` for tests that use cwl:requirements in the input object
    1. `multiple_input` for MultipleInputFeatureRequirement
    1. `networkaccess` for NetworkAccess
    1. `resource` for ResourceRequirement
    1. `scatter` for ScatterFeatureRequirement
    1. `schema_def` for SchemaDefRequirement
    1. `shell_command` for ShellCommandRequirement
    1. `step_input` for StepInputExpressionRequirement
    1. `subworkflow` for SubworkflowRequirement
    1. `timelimit` for ToolTimeLimit
