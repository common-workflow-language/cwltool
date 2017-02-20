==================================================================
Common workflow language tool description reference implementation
==================================================================

CWL Conformance test: |Build Status|

This is the reference implementation of the Common Workflow Language.  It is
intended to be feature complete and provide comprehensive validation of CWL
files as well as provide other tools related to working with CWL.

This is written and tested for Python 2.7.

The reference implementation consists of two packages.  The "cwltool" package
is the primary Python module containing the reference implementation in the
"cwltool" module and console executable by the same name.

The "cwlref-runner" package is optional and provides an additional entry point
under the alias "cwl-runner", which is the implementation-agnostic name for the
default CWL interpreter installed on a host.

Install
-------

Installing the official package from PyPi (will install "cwltool" package as
well)::

  pip install cwlref-runner

If installling alongside another CWL implementation then::

  pip install cwltool

To install from source::

  git clone https://github.com/common-workflow-language/cwltool.git
  cd cwltool && python setup.py install
  cd cwlref-runner && python setup.py install  # co-installing? skip this

Remember, if co-installing multiple CWL implementations then you need to
maintain which implementation ``cwl-runner`` points to via a symbolic file
system link or [another facility](https://wiki.debian.org/DebianAlternatives).

Run on the command line
-----------------------

Simple command::

  cwl-runner [tool-or-workflow-description] [input-job-settings]

Or if you have multiple CWL implementations installed and you want to override
the default cwl-runner use::

  cwltool [tool-or-workflow-description] [input-job-settings]

Use with boot2docker
--------------------
boot2docker is running docker inside a virtual machine and it only mounts ``Users``
on it. The default behavoir of CWL is to create temporary directories under e.g.
``/Var`` which is not accessible to Docker containers.

To run CWL successfully with boot2docker you need to set the ``--tmpdir-prefix``
and ``--tmp-outdir-prefix`` to somewhere under ``/Users``::

    $ cwl-runner --tmp-outdir-prefix=/Users/username/project --tmpdir-prefix=/Users/username/project wc-tool.cwl wc-job.json

.. |Build Status| image:: https://ci.commonwl.org/buildStatus/icon?job=cwltool-conformance
   :target: https://ci.commonwl.org/job/cwltool-conformance/

Tool or workflow loading from remote or local locations
-------------------------------------------------------

``cwltool`` can run tool and workflow descriptions on both local and remote
systems via its support for HTTP[S] URLs.

Input job files and Workflow steps (via the `run` directive) can reference CWL
documents using absolute or relative local filesytem paths. If a relative path
is referenced and that document isn't found in the current directory then the
following locations will be searched:
http://www.commonwl.org/v1.0/CommandLineTool.html#Discovering_CWL_documents_on_a_local_filesystem

Import as a module
------------------

Add::

  import cwltool

to your script.

The easiest way to use cwltool to run a tool or workflow from Python is to use a Factory::

  import cwltool.factory
  fac = cwltool.factory.Factory()

  echo = f.make("echo.cwl")
  result = echo(inp="foo")

  # result["out"] == "foo"


Cwltool Architecture
--------------------

1. Use CWL `load_tool()` to load document.
   1. Fetches the document from file or URL
   1. Applies preprocessing (syntax/identifier expansion and normalization)
   1. Validates the document based on cwlVersion
   1. If necessary, updates the document to latest spec
   1. Constructs a Process object using `make_tool()` callback.  This yields a CommandLineTool, Workflow, or ExpressionTool.  For workflows, this recursively constructs each workflow step.
   1. To construct custom types for CommandLineTool, Workflow, or ExpressionTool, provide a custom `make_tool()`
1. Iterate on the `job()` method of the Process object to get back runnable jobs.
   1. `job()` is a generator method (uses the Python iterator protocol)
   1. Each time the `job()` method is invoked in an iteration, it returns one of: a runnable item (an object with a `run()` method), `None` (indicating there is currently no work ready to run) or end of iteration (indicating the process is complete.)
   1. Invoke the runnable item by calling `run()`.  This runs the tool and gets output.
   1. Output of a process is reported by an output callback.
   1. `job()` may be iterated over multiple times.  It will yield all the work that is currently ready to run and then yield None.
1. "Workflow" objects create a corresponding "WorkflowJob" and "WorkflowJobStep" objects to hold the workflow state for the duration of the job invocation.
   1. The WorkflowJob iterates over each WorkflowJobStep and determines if the inputs the step are ready.
   1. When a step is ready, it constructs an input object for that step and iterates on the `job()` method of the workflow job step.
   1. Each runnable item is yielded back up to top level run loop
   1. When the workflow completes, intermediate files are moved to a final workflow output, intermediate directories are deleted, and the output callback is called.
1. "CommandLineTool" job() objects yield a single runnable object.
   1. The CommandLineTool `job()` method calls `makeJobRunner()` to create a `CommandLineJob` object
   1. The job method configures the CommandLineJob object by setting public attributes
   1. The job method iterates over file and directories inputs to the CommandLineTool and creates a "path map".
   1. Files are mapped from their "resolved" location to a "target" path where they will appear at tool invocation (for example, a location inside a Docker container.)  The target paths are used on the command line.
   1. Files are staged to targets paths using either Docker volume binds (when using containers) or symlinks (if not).  This staging step enables files to be logically rearranged or renamed independent of their source layout.
   1. The run() method of CommandLineJob executes the command line tool or Docker container, waits for it to complete, collects output, and makes the output callback.


Extension points
----------------

* executor
* makeTool
* selectResources
* versionfunc
* make_fs_access
* fetcher_constructor
* resolver
* logger_handler
