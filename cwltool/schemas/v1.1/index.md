# Common Workflow Language Specifications, v1.1

The CWL specifications are divided up into several documents.

The [User Guide](http://www.commonwl.org/user_guide/) provides a gentle
introduction to writing CWL command line tools and workflows.

The [Command Line Tool Description Specification](CommandLineTool.html)
specifies the document schema and execution semantics for wrapping and
executing command line tools.

The [Workflow Description Specification](Workflow.html) specifies the document
schema and execution semantics for composing workflows from components such as
command line tools and other workflows.

The
[Semantic Annotations for Linked Avro Data (SALAD) Specification](SchemaSalad.html)
specifies the preprocessing steps that must be applied when loading CWL
documents and the schema language used to write the above specifications.

Also available are inheritance graphs (as SVG images) for the [Schema Salad object model](salad.svg) and the [CWL object model](cwl.svg).

# Running the CWL conformance tests

Install a CWL runner of your choice. The reference runner can be installed as
the default runner by doing:
```
pip install cwlref-runner
```

Install the CWL test parser:
```
pip install cwltest
```
You may need to activate a virtualenv first, or do a local install by adding `--user` after `install` above.

From within a copy of [this repository](https://github.com/common-workflow-language/cwl-v1.1) (e.g. cwl-v1.1) execute the main test script
```
./run_test.sh
```

If the CWL runner isn't installed as `cwl-runner` then you can specify the name for the runner:
```
./run_test.sh RUNNER=cwltool
```

You can also specify additional options that are specific for the particular CWL runner you are using.
For example, with CWL reference runner you can turn on parallel execution mode:
```
./run_test.sh RUNNER=cwltool EXTRA=--parallel
```

This can be combined with launching more than one CWL conformance test at once with `-j`:
```
./run_test.sh -j4 RUNNER=cwltool EXTRA=--parallel
```

You can list all the tests
```
./run_test.sh -l
```

You can run a particular test
```
./run_test.sh -n23
```


If you are running tests for an unreleased CWL version use the `--enable-dev` flag:
```
./run_test.sh EXTRA=--enable-dev
```


For details of options you can pass to the test script, do:
```
./run_test.sh --help
```

The full test suite takes about 10 minutes to run
