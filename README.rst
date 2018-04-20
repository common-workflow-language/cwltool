==================================================================
Common Workflow Language tool description reference implementation
==================================================================

CWL conformance tests: |Conformance Status| |Linux Status| |Windows Status| |Coverage Status|


.. |Conformance Status| image:: https://ci.commonwl.org/buildStatus/icon?job=cwltool-conformance
   :target: https://ci.commonwl.org/job/cwltool-conformance/

.. |Linux Status| image:: https://img.shields.io/travis/common-workflow-language/cwltool/master.svg?label=Linux%20builds
   :target: https://travis-ci.org/common-workflow-language/cwltool

.. |Windows Status| image:: https://img.shields.io/appveyor/ci/mr-c/cwltool/master.svg?label=Windows%20builds
   :target: https://ci.appveyor.com/project/mr-c/cwltool

.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/common-workflow-language/cwltool.svg
  :target: https://codecov.io/gh/common-workflow-language/cwltool

This is the reference implementation of the Common Workflow Language.  It is
intended to feature complete and provide comprehensive validation of CWL
files as well as provide other tools related to working with CWL.

This is written and tested for `Python <https://www.python.org/>`_ ``2.7 and 3.x {x = 4, 5, 6}``

The reference implementation consists of two packages.  The ``cwltool`` package
is the primary Python module containing the reference implementation in the
``cwltool`` module and console executable by the same name.

The ``cwlref-runner`` package is optional and provides an additional entry point
under the alias ``cwl-runner``, which is the implementation-agnostic name for the
default CWL interpreter installed on a host.

Install
-------

It is highly recommended to setup virtual environment before installing `cwltool`:

.. code:: bash

  virtualenv -p python2 venv   # Create a virtual environment, can use `python3` as well
  source venv/bin/activate     # Activate environment before installing `cwltool`

Installing the official package from PyPi (will install "cwltool" package as
well)

.. code:: bash

  pip install cwlref-runner

If installing alongside another CWL implementation then

.. code:: bash

  pip install cwltool

Or you can install from source:

.. code:: bash

  git clone https://github.com/common-workflow-language/cwltool.git # clone cwltool repo
  cd cwltool         # Switch to source directory
  pip install .      # Install `cwltool` from source
  cwltool --version  # Check if the installation works correctly

Remember, if co-installing multiple CWL implementations then you need to
maintain which implementation ``cwl-runner`` points to via a symbolic file
system link or `another facility <https://wiki.debian.org/DebianAlternatives>`_.

Running tests locally
---------------------

-  Running basic tests ``(/tests)``:

To run the basis tests after installing `cwltool` execute the following:

.. code:: bash

  pip install pytest mock
  py.test --ignore cwltool/schemas/ --pyarg cwltool

To run various tests in all supported Python environments we use `tox <https://github.com/common-workflow-language/cwltool/tree/master/tox.ini>`_. To run the test suite in all supported Python environments
first downloading the complete code repository (see the ``git clone`` instructions above) and then run
the following in the terminal:
``pip install tox; tox``

List of all environment can be seen using:
``tox --listenvs``
and running a specfic test env using:
``tox -e <env name>``
and additionally run a specific test using this format:
``tox -e py36-unit -- tests/test_examples.py::TestParamMatching``

-  Running the entire suite of CWL conformance tests:

The GitHub repository for the CWL specifications contains a script that tests a CWL
implementation against a wide array of valid CWL files using the `cwltest <https://github.com/common-workflow-language/cwltest>`_
program

Instructions for running these tests can be found in the Common Workflow Language Specification repository at https://github.com/common-workflow-language/common-workflow-language/blob/master/CONFORMANCE_TESTS.md

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
on it. The default behavior of CWL is to create temporary directories under e.g.
``/Var`` which is not accessible to Docker containers.

To run CWL successfully with boot2docker you need to set the ``--tmpdir-prefix``
and ``--tmp-outdir-prefix`` to somewhere under ``/Users``::

    $ cwl-runner --tmp-outdir-prefix=/Users/username/project --tmpdir-prefix=/Users/username/project wc-tool.cwl wc-job.json

Using user-space replacements for Docker
----------------------------------------

Some shared computing environments don't support Docker software containers for technical or policy reasons.
As a work around, the CWL reference runner supports using a alternative ``docker`` implementations on Linux
with the ``--user-space-docker-cmd`` option.

One such "user space" friendly docker replacement is ``udocker`` https://github.com/indigo-dc/udocker and another
is ``dx-docker`` https://wiki.dnanexus.com/Developer-Tutorials/Using-Docker-Images

udocker installation: https://github.com/indigo-dc/udocker/blob/master/doc/installation_manual.md#22-install-from-indigo-datacloud-repositories

dx-docker installation: start with the DNAnexus toolkit (see https://wiki.dnanexus.com/Downloads for instructions).

Run `cwltool` just as you normally would, but with the new option, e.g. from the conformance tests:

.. code:: bash

  cwltool --user-space-docker-cmd=udocker https://raw.githubusercontent.com/common-workflow-language/common-workflow-language/master/v1.0/v1.0/test-cwl-out2.cwl https://github.com/common-workflow-language/common-workflow-language/blob/master/v1.0/v1.0/empty.json

or

.. code:: bash

  cwltool --user-space-docker-cmd=dx-docker https://raw.githubusercontent.com/common-workflow-language/common-workflow-language/master/v1.0/v1.0/test-cwl-out2.cwl https://github.com/common-workflow-language/common-workflow-language/blob/master/v1.0/v1.0/empty.json

``cwltool`` can use `Singularity <http://singularity.lbl.gov/>`_ as a Docker container runtime, an experimental feature.
Singularity will run software containers specified in ``DockerRequirement`` and therefore works with Docker images only,
native Singularity images are not supported.
To use Singularity as the Docker container runtime, provide ``--singularity`` command line option to ``cwltool``.


.. code:: bash

  cwltool --singularity https://raw.githubusercontent.com/common-workflow-language/common-workflow-language/master/v1.0/v1.0/v1.0/cat3-tool-mediumcut.cwl https://github.com/common-workflow-language/common-workflow-language/blob/master/v1.0/v1.0/cat-job.json

Tool or workflow loading from remote or local locations
-------------------------------------------------------

``cwltool`` can run tool and workflow descriptions on both local and remote
systems via its support for HTTP[S] URLs.

Input job files and Workflow steps (via the `run` directive) can reference CWL
documents using absolute or relative local filesytem paths. If a relative path
is referenced and that document isn't found in the current directory then the
following locations will be searched:
http://www.commonwl.org/v1.0/CommandLineTool.html#Discovering_CWL_documents_on_a_local_filesystem


Use with GA4GH Tool Registry API
--------------------------------

Cwltool can launch tools directly from `GA4GH Tool Registry API`_ endpoints.

By default, cwltool searches https://dockstore.org/ .  Use --add-tool-registry to add other registries to the search path.

For example ::

  cwltool --non-strict quay.io/collaboratory/dockstore-tool-bamstats:master test.json

and (defaults to latest when a version is not specified) ::

  cwltool --non-strict quay.io/collaboratory/dockstore-tool-bamstats test.json

For this example, grab the test.json (and input file) from https://github.com/CancerCollaboratory/dockstore-tool-bamstats

.. _`GA4GH Tool Registry API`: https://github.com/ga4gh/tool-registry-schemas

Import as a module
------------------

Add

.. code:: python

  import cwltool

to your script.

The easiest way to use cwltool to run a tool or workflow from Python is to use a Factory

.. code:: python

  import cwltool.factory
  fac = cwltool.factory.Factory()

  echo = f.make("echo.cwl")
  result = echo(inp="foo")

  # result["out"] == "foo"

Leveraging SoftwareRequirements (Beta)
--------------------------------------

CWL tools may be decorated with ``SoftwareRequirement`` hints that cwltool
may in turn use to resolve to packages in various package managers or
dependency management systems such as `Environment Modules
<http://modules.sourceforge.net/>`__.

Utilizing ``SoftwareRequirement`` hints using cwltool requires an optional
dependency, for this reason be sure to use specify the ``deps`` modifier when
installing cwltool. For instance::

  $ pip install 'cwltool[deps]'

Installing cwltool in this fashion enables several new command line options.
The most general of these options is ``--beta-dependency-resolvers-configuration``.
This option allows one to specify a dependency resolvers configuration file.
This file may be specified as either XML or YAML and very simply describes various
plugins to enable to "resolve" ``SoftwareRequirement`` dependencies.

To discuss some of these plugins and how to configure them, first consider the
following ``hint`` definition for an example CWL tool.

.. code:: yaml

  SoftwareRequirement:
    packages:
    - package: seqtk
      version:
      - r93

Now imagine deploying cwltool on a cluster with Software Modules installed
and that a ``seqtk`` module is available at version ``r93``. This means cluster
users likely won't have the binary ``seqtk`` on their ``PATH`` by default, but after
sourcing this module with the command ``modulecmd sh load seqtk/r93`` ``seqtk`` is
available on the ``PATH``. A simple dependency resolvers configuration file, called
``dependency-resolvers-conf.yml`` for instance, that would enable cwltool to source
the correct module environment before executing the above tool would simply be:

.. code:: yaml

  - type: modules

The outer list indicates that one plugin is being enabled, the plugin parameters are
defined as a dictionary for this one list item. There is only one required parameter
for the plugin above, this is ``type`` and defines the plugin type. This parameter
is required for all plugins. The available plugins and the parameters
available for each are documented (incompletely) `here
<https://docs.galaxyproject.org/en/latest/admin/dependency_resolvers.html>`__.
Unfortunately, this documentation is in the context of Galaxy tool
``requirement`` s instead of CWL ``SoftwareRequirement`` s, but the concepts map fairly directly.

cwltool is distributed with an example of such seqtk tool and sample corresponding
job. It could executed from the cwltool root using a dependency resolvers
configuration file such as the above one using the command::

  cwltool --beta-dependency-resolvers-configuration /path/to/dependency-resolvers-conf.yml \
      tests/seqtk_seq.cwl \
      tests/seqtk_seq_job.json

This example demonstrates both that cwltool can leverage
existing software installations and also handle workflows with dependencies
on different versions of the same software and libraries. However the above
example does require an existing module setup so it is impossible to test this example
"out of the box" with cwltool. For a more isolated test that demonstrates all
the same concepts - the resolver plugin type ``galaxy_packages`` can be used.

"Galaxy packages" are a lighter weight alternative to Environment Modules that are
really just defined by a way to lay out directories into packages and versions
to find little scripts that are sourced to modify the environment. They have
been used for years in Galaxy community to adapt Galaxy tools to cluster
environments but require neither knowledge of Galaxy nor any special tools to
setup. These should work just fine for CWL tools.

The cwltool source code repository's test directory is setup with a very simple
directory that defines a set of "Galaxy  packages" (but really just defines one
package named ``random-lines``). The directory layout is simply::

  tests/test_deps_env/
    random-lines/
      1.0/
        env.sh

If the ``galaxy_packages`` plugin is enabled and pointed at the
``tests/test_deps_env`` directory in cwltool's root and a ``SoftwareRequirement``
such as the following is encountered.

.. code:: yaml

  hints:
    SoftwareRequirement:
      packages:
      - package: 'random-lines'
        version:
        - '1.0'

Then cwltool will simply find that ``env.sh`` file and source it before executing
the corresponding tool. That ``env.sh`` script is only responsible for modifying
the job's ``PATH`` to add the required binaries.

This is a full example that works since resolving "Galaxy packages" has no
external requirements. Try it out by executing the following command from cwltool's
root directory::

  cwltool --beta-dependency-resolvers-configuration tests/test_deps_env_resolvers_conf.yml \
      tests/random_lines.cwl \
      tests/random_lines_job.json

The resolvers configuration file in the above example was simply:

.. code:: yaml

  - type: galaxy_packages
    base_path: ./tests/test_deps_env

It is possible that the ``SoftwareRequirement`` s in a given CWL tool will not
match the module names for a given cluster. Such requirements can be re-mapped
to specific deployed packages and/or versions using another file specified using
the resolver plugin parameter `mapping_files`. We will
demonstrate this using `galaxy_packages` but the concepts apply equally well
to Environment Modules or Conda packages (described below) for instance.

So consider the resolvers configuration file
(`tests/test_deps_env_resolvers_conf_rewrite.yml`):

.. code:: yaml

  - type: galaxy_packages
    base_path: ./tests/test_deps_env
    mapping_files: ./tests/test_deps_mapping.yml

And the corresponding mapping configuraiton file (`tests/test_deps_mapping.yml`):

.. code:: yaml

  - from:
      name: randomLines
      version: 1.0.0-rc1
    to:
      name: random-lines
      version: '1.0'

This is saying if cwltool encounters a requirement of ``randomLines`` at version
``1.0.0-rc1`` in a tool, to rewrite to our specific plugin as ``random-lines`` at
version ``1.0``. cwltool has such a test tool called ``random_lines_mapping.cwl``
that contains such a source ``SoftwareRequirement``. To try out this example with
mapping, execute the following command from the cwltool root directory::

  cwltool --beta-dependency-resolvers-configuration tests/test_deps_env_resolvers_conf_rewrite.yml \
      tests/random_lines_mapping.cwl \
      tests/random_lines_job.json

The previous examples demonstrated leveraging existing infrastructure to
provide requirements for CWL tools. If instead a real package manager is used
cwltool has the oppertunity to install requirements as needed. While initial
support for Homebrew/Linuxbrew plugins is available, the most developed such
plugin is for the `Conda <https://conda.io/docs/#>`__ package manager. Conda has the nice properties
of allowing multiple versions of a package to be installed simultaneously,
not requiring evalated permissions to install Conda itself or packages using
Conda, and being cross platform. For these reasons, cwltool may run as a normal
user, install its own Conda environment and manage multiple versions of Conda packages
on both Linux and Mac OS X.

The Conda plugin can be endlessly configured, but a sensible set of defaults
that has proven a powerful stack for dependency management within the Galaxy tool
development ecosystem can be enabled by simply passing cwltool the
``--beta-conda-dependencies`` flag.

With this we can use the seqtk example above without Docker and without
any externally managed services - cwltool should install everything it needs
and create an environment for the tool. Try it out with the follwing command::

  cwltool --beta-conda-dependencies tests/seqtk_seq.cwl tests/seqtk_seq_job.json

The CWL specification allows URIs to be attached to ``SoftwareRequirement`` s
that allow disambiguation of package names. If the mapping files described above
allow deployers to adapt tools to their infrastructure, this mechanism allows
tools to adapt their requirements to multiple package managers. To demonstrate
this within the context of the seqtk, we can simply break the package name we
use and then specify a specific Conda package as follows:

.. code:: yaml

  hints:
    SoftwareRequirement:
      packages:
      - package: seqtk_seq
        version:
        - '1.2'
        specs:
        - https://anaconda.org/bioconda/seqtk
        - https://packages.debian.org/sid/seqtk

The example can be executed using the command::

  cwltool --beta-conda-dependencies tests/seqtk_seq_wrong_name.cwl tests/seqtk_seq_job.json

The plugin framework for managing resolution of these software requirements
as maintained as part of `galaxy-lib <https://github.com/galaxyproject/galaxy-lib>`__ - a small, portable subset of the Galaxy
project. More information on configuration and implementation can be found
at the following links:

- `Dependency Resolvers in Galaxy <https://docs.galaxyproject.org/en/latest/admin/dependency_resolvers.html>`__
- `Conda for [Galaxy] Tool Dependencies <https://docs.galaxyproject.org/en/latest/admin/conda_faq.html>`__
- `Mapping Files - Implementation <https://github.com/galaxyproject/galaxy/commit/495802d229967771df5b64a2f79b88a0eaf00edb>`__
- `Specifications - Implementation <https://github.com/galaxyproject/galaxy/commit/81d71d2e740ee07754785306e4448f8425f890bc>`__
- `Initial cwltool Integration Pull Request <https://github.com/common-workflow-language/cwltool/pull/214>`__

Overriding workflow requirements at load time
---------------------------------------------

Sometimes a workflow needs additional requirements to run in a particular
environment or with a particular dataset.  To avoid the need to modify the
underlying workflow, cwltool supports requirement "overrides".

The format of the "overrides" object is a mapping of item identifier (workflow,
workflow step, or command line tool) to the process requirements that should be applied.

.. code:: yaml

  cwltool:overrides:
    echo.cwl:
      requirements:
        EnvVarRequirement:
          envDef:
            MESSAGE: override_value

Overrides can be specified either on the command line, or as part of the job
input document.  Workflow steps are identified using the name of the workflow
file followed by the step name as a document fragment identifier "#id".
Override identifiers are relative to the toplevel workflow document.

.. code:: bash

  cwltool --overrides overrides.yml my-tool.cwl my-job.yml

.. code:: yaml

  input_parameter1: value1
  input_parameter2: value2
  cwltool:overrides:
    workflow.cwl#step1:
      requirements:
        EnvVarRequirement:
          envDef:
            MESSAGE: override_value

.. code:: bash

  cwltool my-tool.cwl my-job-with-overrides.yml


CWL Tool Control Flow
---------------------

Technical outline of how cwltool works internally, for maintainers.

#. Use CWL ``load_tool()`` to load document.

   #. Fetches the document from file or URL
   #. Applies preprocessing (syntax/identifier expansion and normalization)
   #. Validates the document based on cwlVersion
   #. If necessary, updates the document to latest spec
   #. Constructs a Process object using ``make_tool()``` callback.  This yields a
      CommandLineTool, Workflow, or ExpressionTool.  For workflows, this
      recursively constructs each workflow step.
   #. To construct custom types for CommandLineTool, Workflow, or
      ExpressionTool, provide a custom ``make_tool()``

#. Iterate on the ``job()`` method of the Process object to get back runnable jobs.

   #. ``job()`` is a generator method (uses the Python iterator protocol)
   #. Each time the ``job()`` method is invoked in an iteration, it returns one
      of: a runnable item (an object with a ``run()`` method), ``None`` (indicating
      there is currently no work ready to run) or end of iteration (indicating
      the process is complete.)
   #. Invoke the runnable item by calling ``run()``.  This runs the tool and gets output.
   #. Output of a process is reported by an output callback.
   #. ``job()`` may be iterated over multiple times.  It will yield all the work
      that is currently ready to run and then yield None.

#. ``Workflow`` objects create a corresponding ``WorkflowJob`` and ``WorkflowJobStep`` objects to hold the workflow state for the duration of the job invocation.

   #. The WorkflowJob iterates over each WorkflowJobStep and determines if the
      inputs the step are ready.
   #. When a step is ready, it constructs an input object for that step and
      iterates on the ``job()`` method of the workflow job step.
   #. Each runnable item is yielded back up to top level run loop
   #. When a step job completes and receives an output callback, the
      job outputs are assigned to the output of the workflow step.
   #. When all steps are complete, the intermediate files are moved to a final
      workflow output, intermediate directories are deleted, and the output
      callback for the workflow is called.

#. ``CommandLineTool`` job() objects yield a single runnable object.

   #. The CommandLineTool ``job()`` method calls ``makeJobRunner()`` to create a
      ``CommandLineJob`` object
   #. The job method configures the CommandLineJob object by setting public
      attributes
   #. The job method iterates over file and directories inputs to the
      CommandLineTool and creates a "path map".
   #. Files are mapped from their "resolved" location to a "target" path where
      they will appear at tool invocation (for example, a location inside a
      Docker container.)  The target paths are used on the command line.
   #. Files are staged to targets paths using either Docker volume binds (when
      using containers) or symlinks (if not).  This staging step enables files
      to be logically rearranged or renamed independent of their source layout.
   #. The ``run()`` method of CommandLineJob executes the command line tool or
      Docker container, waits for it to complete, collects output, and makes
      the output callback.


Extension points
----------------

The following functions can be provided to main(), to load_tool(), or to the
executor to override or augment the listed behaviors.

executor
  ::

    executor(tool, job_order_object, **kwargs)
      (Process, Dict[Text, Any], **Any) -> Tuple[Dict[Text, Any], Text]

  A toplevel workflow execution loop, should synchronously execute a process
  object and return an output object.

makeTool
  ::

    makeTool(toolpath_object, **kwargs)
      (Dict[Text, Any], **Any) -> Process

  Construct a Process object from a document.

selectResources
  ::

    selectResources(request)
      (Dict[Text, int]) -> Dict[Text, int]

  Take a resource request and turn it into a concrete resource assignment.

versionfunc
  ::

    ()
      () -> Text

  Return version string.

make_fs_access
  ::

    make_fs_access(basedir)
      (Text) -> StdFsAccess

  Return a file system access object.

fetcher_constructor
  ::

    fetcher_constructor(cache, session)
      (Dict[unicode, unicode], requests.sessions.Session) -> Fetcher

  Construct a Fetcher object with the supplied cache and HTTP session.

resolver
  ::

    resolver(document_loader, document)
      (Loader, Union[Text, dict[Text, Any]]) -> Text

  Resolve a relative document identifier to an absolute one which can be fetched.

logger_handler
  ::

    logger_handler
      logging.Handler

  Handler object for logging.
