# Common workflow language conformance test suite

The conformance tests are intended to test feature coverage of a CWL
implementation.  It uses the module cwltest from https://github.com/common-workflow-language/cwltest/.

## Usage

```bash
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

```bash
$ ./run_test.sh RUNNER=cwltool -n15 EXTRA=--parallel
Test [15/49]
All tests passed
```

## Notes

_NOTE_: For running on OSX systems, you'll need to install coreutils via brew. This will add to your
system some needed GNU-like tools like `greadlink`.

1. If you haven't already, install [brew](http://brew.sh/) package manager in your mac
2. Run `brew install coreutils`

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
