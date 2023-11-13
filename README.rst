#############################################################################################
``cwltool``: The reference reference implementation of the Common Workflow Language standards
#############################################################################################

|Linux Status| |Coverage Status| |Docs Status|

PyPI: |PyPI Version| |PyPI Downloads Month| |Total PyPI Downloads|

Conda: |Conda Version| |Conda Installs|

Debian: |Debian Testing package| |Debian Stable package|

Quay.io (Docker): |Quay.io Container|

.. |Linux Status| image:: https://github.com/common-workflow-language/cwltool/actions/workflows/ci-tests.yml/badge.svg?branch=main
   :target: https://github.com/common-workflow-language/cwltool/actions/workflows/ci-tests.yml

.. |Debian Stable package| image:: https://badges.debian.net/badges/debian/stable/cwltool/version.svg
   :target: https://packages.debian.org/stable/cwltool

.. |Debian Testing package| image:: https://badges.debian.net/badges/debian/testing/cwltool/version.svg
   :target: https://packages.debian.org/testing/cwltool

.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/common-workflow-language/cwltool.svg
   :target: https://codecov.io/gh/common-workflow-language/cwltool

.. |PyPI Version| image:: https://badge.fury.io/py/cwltool.svg
   :target: https://badge.fury.io/py/cwltool

.. |PyPI Downloads Month| image:: https://pepy.tech/badge/cwltool/month
   :target: https://pepy.tech/project/cwltool

.. |Total PyPI Downloads| image:: https://static.pepy.tech/personalized-badge/cwltool?period=total&units=international_system&left_color=black&right_color=orange&left_text=Total%20PyPI%20Downloads
   :target: https://pepy.tech/project/cwltool

.. |Conda Version| image:: https://anaconda.org/conda-forge/cwltool/badges/version.svg
   :target: https://anaconda.org/conda-forge/cwltool

.. |Conda Installs| image:: https://anaconda.org/conda-forge/cwltool/badges/downloads.svg
   :target: https://anaconda.org/conda-forge/cwltool

.. |Quay.io Container| image:: https://quay.io/repository/commonwl/cwltool/status
   :target: https://quay.io/repository/commonwl/cwltool

.. |Docs Status| image:: https://readthedocs.org/projects/cwltool/badge/?version=latest
   :target: https://cwltool.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

This is the reference implementation of the `Common Workflow Language open
standards <https://www.commonwl.org/>`_.  It is intended to be feature complete
and provide comprehensive validation of CWL
files as well as provide other tools related to working with CWL.

``cwltool`` is written and tested for
`Python <https://www.python.org/>`_ ``3.x {x = 6, 8, 9, 10, 11}``

The reference implementation consists of two packages.  The ``cwltool`` package
is the primary Python module containing the reference implementation in the
``cwltool`` module and console executable by the same name.

The ``cwlref-runner`` package is optional and provides an additional entry point
under the alias ``cwl-runner``, which is the implementation-agnostic name for the
default CWL interpreter installed on a host.

``cwltool`` is provided by the CWL project, `a member project of Software Freedom Conservancy <https://sfconservancy.org/news/2018/apr/11/cwl-new-member-project/>`_
and our `many contributors <https://github.com/common-workflow-language/cwltool/graphs/contributors>`_.

.. contents:: Table of Contents

*******
Install
*******

``cwltool`` packages
====================

Your operating system may offer cwltool directly. For `Debian <https://tracker.debian.org/pkg/cwltool>`_, `Ubuntu <https://launchpad.net/ubuntu/+source/cwltool>`_,
and similar Linux distribution try

.. code:: bash

   sudo apt-get install cwltool

If you encounter an error, first try to update package information by using

.. code:: bash

   sudo apt-get update

If you are running macOS X or other UNIXes and you want to use packages prepared by the conda-forge project, then
please follow the install instructions for `conda-forge <https://conda-forge.org/#about>`_ (if you haven't already) and then

.. code:: bash

   conda install -c conda-forge cwltool

All of the above methods of installing ``cwltool`` use packages that might contain bugs already fixed in newer versions or be missing desired features.
If the packaged version of ``cwltool`` available to you is too old, then we recommend installing using ``pip`` and ``venv``

.. code:: bash

   python3 -m venv env      # Create a virtual environment named 'env' in the current directory
   source env/bin/activate  # Activate environment before installing `cwltool`

Then install the latest ``cwlref-runner`` package from PyPi (which will install the latest ``cwltool`` package as
well)

.. code:: bash

  pip install cwlref-runner

If installing alongside another CWL implementation (like ``toil-cwl-runner`` or ``arvados-cwl-runner``) then instead run

.. code:: bash

  pip install cwltool

MS Windows users
================

1. `Install Windows Subsystem for Linux 2 and Docker Desktop <https://docs.docker.com/docker-for-windows/wsl/#prerequisites>`_. 
2. `Install Debian from the Microsoft Store <https://www.microsoft.com/en-us/p/debian/9msvkqc78pk6>`_.
3. Set Debian as your default WSL 2 distro: ``wsl --set-default debian``.
4. Return to the Docker Desktop, choose ``Settings`` → ``Resources`` → ``WSL Integration`` and under "Enable integration with additional distros" select "Debian",
5. Reboot if you have not yet already.
6. Launch Debian and follow the Linux instructions above (``apt-get install cwltool`` or use the ``venv`` method)

Network problems from within WSL2? Try `these instructions <https://github.com/microsoft/WSL/issues/4731#issuecomment-702176954>`_ followed by ``wsl --shutdown``.

``cwltool`` development version
===============================

Or you can skip the direct ``pip`` commands above and install the latest development version of ``cwltool``:

.. code:: bash

  git clone https://github.com/common-workflow-language/cwltool.git # clone (copy) the cwltool git repository
  cd cwltool           # Change to source directory that git clone just downloaded
  pip install .[deps]  # Installs ``cwltool`` from source
  cwltool --version    # Check if the installation works correctly

Remember, if co-installing multiple CWL implementations, then you need to
maintain which implementation ``cwl-runner`` points to via a symbolic file
system link or `another facility <https://wiki.debian.org/DebianAlternatives>`_.

Recommended Software
====================

We strongly suggested to have the following installed:

* One of the following software container engines

  * `Podman <https://podman.io/getting-started/installation>`_
  * `Docker <https://docs.docker.com/engine/install/>`_
  * Singularity/Apptainer: See `Using Singularity`_
  * udocker: See `Using uDocker`_

* `node.js <https://nodejs.org/en/download/>`_ for evaluating CWL Expressions quickly
  (required for `udocker` users, optional but recommended for the other container engines).

Without these, some examples in the CWL tutorials at http://www.commonwl.org/user_guide/ may not work.

***********************
Run on the command line
***********************

Simple command::

  cwl-runner my_workflow.cwl my_inputs.yaml

Or if you have multiple CWL implementations installed and you want to override
the default cwl-runner then use::

  cwltool my_workflow.cwl my_inputs.yml

You can set cwltool options in the environment with ``CWLTOOL_OPTIONS``,
these will be inserted at the beginning of the command line::

  export CWLTOOL_OPTIONS="--debug"

Use with boot2docker on macOS
=============================
boot2docker runs Docker inside a virtual machine, and it only mounts ``Users``
on it. The default behavior of CWL is to create temporary directories under e.g.
``/Var`` which is not accessible to Docker containers.

To run CWL successfully with boot2docker you need to set the ``--tmpdir-prefix``
and ``--tmp-outdir-prefix`` to somewhere under ``/Users``::

    $ cwl-runner --tmp-outdir-prefix=/Users/username/project --tmpdir-prefix=/Users/username/project wc-tool.cwl wc-job.json

Using uDocker
=============

Some shared computing environments don't support Docker software containers for technical or policy reasons.
As a workaround, the CWL reference runner supports using the `udocker <https://github.com/indigo-dc/udocker>`_
program on Linux using ``--udocker``.

udocker installation: https://indigo-dc.github.io/udocker/installation_manual.html

Run `cwltool` just as you usually would, but with ``--udocker`` prior to the workflow path:

.. code:: bash

  cwltool --udocker https://github.com/common-workflow-language/common-workflow-language/raw/main/v1.0/v1.0/test-cwl-out2.cwl https://github.com/common-workflow-language/common-workflow-language/raw/main/v1.0/v1.0/empty.json

As was mentioned in the `Recommended Software`_ section,

Using Singularity
=================

``cwltool`` can also use `Singularity <https://github.com/hpcng/singularity/releases/>`_ version 2.6.1
or later as a Docker container runtime.
``cwltool`` with Singularity will run software containers specified in
``DockerRequirement`` and therefore works with Docker images only, native
Singularity images are not supported. To use Singularity as the Docker container
runtime, provide ``--singularity`` command line option to ``cwltool``.
With Singularity, ``cwltool`` can pass all CWL v1.0 conformance tests, except
those involving Docker container ENTRYPOINTs.

Example

.. code:: bash

  cwltool --singularity https://github.com/common-workflow-language/common-workflow-language/raw/main/v1.0/v1.0/cat3-tool-mediumcut.cwl https://github.com/common-workflow-language/common-workflow-language/raw/main/v1.0/v1.0/cat-job.json

Running a tool or workflow from remote or local locations
=========================================================

``cwltool`` can run tool and workflow descriptions on both local and remote
systems via its support for HTTP[S] URLs.

Input job files and Workflow steps (via the `run` directive) can reference CWL
documents using absolute or relative local filesystem paths. If a relative path
is referenced and that document isn't found in the current directory, then the
following locations will be searched:
http://www.commonwl.org/v1.0/CommandLineTool.html#Discovering_CWL_documents_on_a_local_filesystem

You can also use `cwldep <https://github.com/common-workflow-language/cwldep>`_
to manage dependencies on external tools and workflows.

Overriding workflow requirements at load time
=============================================

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
Override identifiers are relative to the top-level workflow document.

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


Combining parts of a workflow into a single document
====================================================

Use ``--pack`` to combine a workflow made up of multiple files into a
single compound document.  This operation takes all the CWL files
referenced by a workflow and builds a new CWL document with all
Process objects (CommandLineTool and Workflow) in a list in the
``$graph`` field.  Cross references (such as ``run:`` and ``source:``
fields) are updated to internal references within the new packed
document.  The top-level workflow is named ``#main``.

.. code:: bash

  cwltool --pack my-wf.cwl > my-packed-wf.cwl


Running only part of a workflow
===============================

You can run a partial workflow with the ``--target`` (``-t``) option.  This
takes the name of an output parameter, workflow step, or input
parameter in the top-level workflow.  You may provide multiple
targets.

.. code:: bash

  cwltool --target step3 my-wf.cwl

If a target is an output parameter, it will only run only the steps
that contribute to that output.  If a target is a workflow step, it
will run the workflow starting from that step.  If a target is an
input parameter, it will only run the steps connected to
that input.

Use ``--print-targets`` to get a listing of the targets of a workflow.
To see which steps will run, use ``--print-subgraph`` with
``--target`` to get a printout of the workflow subgraph for the
selected targets.

.. code:: bash

  cwltool --print-targets my-wf.cwl

  cwltool --target step3 --print-subgraph my-wf.cwl > my-wf-starting-from-step3.cwl


Visualizing a CWL document
==========================

The ``--print-dot`` option will print a file suitable for Graphviz ``dot`` program.  Here is a bash onliner to generate a Scalable Vector Graphic (SVG) file:

.. code:: bash

  cwltool --print-dot my-wf.cwl | dot -Tsvg > my-wf.svg

Modeling a CWL document as RDF
==============================

CWL documents can be expressed as RDF triple graphs.

.. code:: bash

  cwltool --print-rdf --rdf-serializer=turtle mywf.cwl


Environment Variables in cwltool
================================

This reference implementation supports several ways of setting
environment variables for tools, in addition to the standard
``EnvVarRequirement``. The sequence of steps applied to create the
environment is:

0. If the ``--preserve-entire-environment`` flag is present, then begin with the current
   environment, else begin with an empty environment.

1. Add any variables specified by ``--preserve-environment`` option(s).

2. Set ``TMPDIR`` and ``HOME`` per `the CWL v1.0+ CommandLineTool specification <https://www.commonwl.org/v1.0/CommandLineTool.html#Runtime_environment>`_.

3. Apply any ``EnvVarRequirement`` from the ``CommandLineTool`` description.

4. Apply any manipulations required by any ``cwltool:MPIRequirement`` extensions.

5. Substitute any secrets required by ``Secrets`` extension.

6. Modify the environment in response to ``SoftwareRequirement`` (see below).


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
This option allows one to specify a dependency resolver's configuration file.
This file may be specified as either XML or YAML and very simply describes various
plugins to enable to "resolve" ``SoftwareRequirement`` dependencies.

Using these hints will allow cwltool to modify the environment in
which your tool runs, for example by loading one or more Environment
Modules. The environment is constructed as above, then the environment
may modified by the selected tool resolver.  This currently means that
you cannot override any environment variables set by the selected tool
resolver. Note that the environment given to the configured dependency
resolver has the variable `_CWLTOOL` set to `1` to allow introspection.

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

"Galaxy packages" are a lighter-weight alternative to Environment Modules that are
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
to specific deployed packages or versions using another file specified using
the resolver plugin parameter `mapping_files`. We will
demonstrate this using `galaxy_packages,` but the concepts apply equally well
to Environment Modules or Conda packages (described below), for instance.

So consider the resolvers configuration file.
(`tests/test_deps_env_resolvers_conf_rewrite.yml`):

.. code:: yaml

  - type: galaxy_packages
    base_path: ./tests/test_deps_env
    mapping_files: ./tests/test_deps_mapping.yml

And the corresponding mapping configuration file (`tests/test_deps_mapping.yml`):

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
cwltool has the opportunity to install requirements as needed. While initial
support for Homebrew/Linuxbrew plugins is available, the most developed such
plugin is for the `Conda <https://conda.io/docs/#>`__ package manager. Conda has the nice properties
of allowing multiple versions of a package to be installed simultaneously,
not requiring evaluated permissions to install Conda itself or packages using
Conda, and being cross-platform. For these reasons, cwltool may run as a normal
user, install its own Conda environment and manage multiple versions of Conda packages
on Linux and Mac OS X.

The Conda plugin can be endlessly configured, but a sensible set of defaults
that has proven a powerful stack for dependency management within the Galaxy tool
development ecosystem can be enabled by simply passing cwltool the
``--beta-conda-dependencies`` flag.

With this, we can use the seqtk example above without Docker or any externally managed services - cwltool should install everything it needs
and create an environment for the tool. Try it out with the following command::

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

The plugin framework for managing the resolution of these software requirements
as maintained as part of `galaxy-tool-util <https://github.com/galaxyproject/galaxy/tree/dev/packages/tool_util>`__ - a small,
portable subset of the Galaxy project. More information on configuration and implementation can be found
at the following links:

- `Dependency Resolvers in Galaxy <https://docs.galaxyproject.org/en/latest/admin/dependency_resolvers.html>`__
- `Conda for [Galaxy] Tool Dependencies <https://docs.galaxyproject.org/en/latest/admin/conda_faq.html>`__
- `Mapping Files - Implementation <https://github.com/galaxyproject/galaxy/commit/495802d229967771df5b64a2f79b88a0eaf00edb>`__
- `Specifications - Implementation <https://github.com/galaxyproject/galaxy/commit/81d71d2e740ee07754785306e4448f8425f890bc>`__
- `Initial cwltool Integration Pull Request <https://github.com/common-workflow-language/cwltool/pull/214>`__

Use with GA4GH Tool Registry API
================================

Cwltool can launch tools directly from `GA4GH Tool Registry API`_ endpoints.

By default, cwltool searches https://dockstore.org/ .  Use ``--add-tool-registry`` to add other registries to the search path.

For example ::

  cwltool quay.io/collaboratory/dockstore-tool-bamstats:develop test.json

and (defaults to latest when a version is not specified) ::

  cwltool quay.io/collaboratory/dockstore-tool-bamstats test.json

For this example, grab the test.json (and input file) from https://github.com/CancerCollaboratory/dockstore-tool-bamstats ::

  wget https://dockstore.org/api/api/ga4gh/v2/tools/quay.io%2Fbriandoconnor%2Fdockstore-tool-bamstats/versions/develop/PLAIN-CWL/descriptor/test.json
  wget https://github.com/CancerCollaboratory/dockstore-tool-bamstats/raw/develop/rna.SRR948778.bam


.. _`GA4GH Tool Registry API`: https://github.com/ga4gh/tool-registry-schemas

Running MPI-based tools that need to be launched
================================================

Cwltool supports an extension to the CWL spec
``http://commonwl.org/cwltool#MPIRequirement``. When the tool
definition has this in its ``requirements``/``hints`` section, and
cwltool has been run with ``--enable-ext``, then the tool's command
line will be extended with the commands needed to launch it with
``mpirun`` or similar. You can specify the number of processes to
start as either a literal integer or an expression (that will result
in an integer). For example::

  #!/usr/bin/env cwl-runner
  cwlVersion: v1.1
  class: CommandLineTool
  $namespaces:
    cwltool: "http://commonwl.org/cwltool#"
  requirements:
    cwltool:MPIRequirement:
      processes: $(inputs.nproc)
  inputs:
    nproc:
      type: int

Interaction with containers: the MPIRequirement currently prepends its
commands to the front of the command line that is constructed. If you
wish to run a containerized application in parallel, for simple use
cases, this does work with Singularity, depending upon the platform
setup. However, this combination should be considered "alpha" -- please
do report any issues you have! This does not work with Docker at the
moment. (More precisely, you get `n` copies of the same single process
image run at the same time that cannot communicate with each other.)

The host-specific parameters are configured in a simple YAML file
(specified with the ``--mpi-config-file`` flag). The allowed keys are
given in the following table; all are optional.

+----------------+------------------+----------+------------------------------+
| Key            | Type             | Default  | Description                  |
+================+==================+==========+==============================+
| runner         | str              | "mpirun" | The primary command to use.  |
+----------------+------------------+----------+------------------------------+
| nproc_flag     | str              | "-n"     | Flag to set number of        |
|                |                  |          | processes to start.          |
+----------------+------------------+----------+------------------------------+
| default_nproc  | int              | 1        | Default number of processes. |
+----------------+------------------+----------+------------------------------+
| extra_flags    | List[str]        | []       | A list of any other flags to |
|                |                  |          | be added to the runner's     |
|                |                  |          | command line before          |
|                |                  |          | the ``baseCommand``.         |
+----------------+------------------+----------+------------------------------+
| env_pass       | List[str]        | []       | A list of environment        |
|                |                  |          | variables that should be     |
|                |                  |          | passed from the host         |
|                |                  |          | environment through to the   |
|                |                  |          | tool (e.g., giving the       |
|                |                  |          | node list as set by your     |
|                |                  |          | scheduler).                  |
+----------------+------------------+----------+------------------------------+
| env_pass_regex | List[str]        | []       | A list of python regular     |
|                |                  |          | expressions that will be     |
|                |                  |          | matched against the host's   |
|                |                  |          | environment. Those that match|
|                |                  |          | will be passed through.      |
+----------------+------------------+----------+------------------------------+
| env_set        | Mapping[str,str] | {}       | A dictionary whose keys are  |
|                |                  |          | the environment variables set|
|                |                  |          | and the values being the     |
|                |                  |          | values.                      |
+----------------+------------------+----------+------------------------------+


Enabling Fast Parser (experimental)
===================================

For very large workflows, `cwltool` can spend a lot of time in
initialization, before the first step runs.  There is an experimental
flag ``--fast-parser`` which can dramatically reduce the
initialization overhead, however as of this writing it has several limitations:

- Error reporting in general is worse than the standard parser, you will want to use it with workflows that you know are already correct.

- It does not check for dangling links (these will become runtime errors instead of loading errors)

- Several other cases fail, as documented in https://github.com/common-workflow-language/cwltool/pull/1720

***********
Development
***********

Running tests locally
=====================

-  Running basic tests ``(/tests)``:

To run the basic tests after installing `cwltool` execute the following:

.. code:: bash

  pip install -rtest-requirements.txt
  pytest   ## N.B. This requires node.js or docker to be available

To run various tests in all supported Python environments, we use `tox <https://github.com/common-workflow-language/cwltool/tree/main/tox.ini>`_. To run the test suite in all supported Python environments
first clone the complete code repository (see the ``git clone`` instructions above) and then run
the following in the terminal:
``pip install "tox<4"; tox -p``

List of all environment can be seen using:
``tox --listenvs``
and running a specific test env using:
``tox -e <env name>``
and additionally run a specific test using this format:
``tox -e py310-unit -- -v tests/test_examples.py::test_scandeps``

-  Running the entire suite of CWL conformance tests:

The GitHub repository for the CWL specifications contains a script that tests a CWL
implementation against a wide array of valid CWL files using the `cwltest <https://github.com/common-workflow-language/cwltest>`_
program

Instructions for running these tests can be found in the Common Workflow Language Specification repository at https://github.com/common-workflow-language/common-workflow-language/blob/main/CONFORMANCE_TESTS.md .

Import as a module
==================

Add

.. code:: python

  import cwltool

to your script.

The easiest way to use cwltool to run a tool or workflow from Python is to use a Factory

.. code:: python

  import cwltool.factory
  fac = cwltool.factory.Factory()

  echo = fac.make("echo.cwl")
  result = echo(inp="foo")

  # result["out"] == "foo"


CWL Tool Control Flow
=====================

Technical outline of how cwltool works internally, for maintainers.

#. Use CWL ``load_tool()`` to load document.

   #. Fetches the document from file or URL
   #. Applies preprocessing (syntax/identifier expansion and normalization)
   #. Validates the document based on cwlVersion
   #. If necessary, updates the document to the latest spec
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
   #. An output callback reports the output of a process.
   #. ``job()`` may be iterated over multiple times.  It will yield all the work
      that is currently ready to run and then yield None.

#. ``Workflow`` objects create a corresponding ``WorkflowJob`` and ``WorkflowJobStep`` objects to hold the workflow state for the duration of the job invocation.

   #. The WorkflowJob iterates over each WorkflowJobStep and determines if the
      inputs the step are ready.
   #. When a step is ready, it constructs an input object for that step and
      iterates on the ``job()`` method of the workflow job step.
   #. Each runnable item is yielded back up to top-level run loop
   #. When a step job completes and receives an output callback, the
      job outputs are assigned to the output of the workflow step.
   #. When all steps are complete, the intermediate files are moved to a final
      workflow output, intermediate directories are deleted, and the workflow's output callback is called.

#. ``CommandLineTool`` job() objects yield a single runnable object.

   #. The CommandLineTool ``job()`` method calls ``make_job_runner()`` to create a
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
================

The following functions can be passed to main() to override or augment
the listed behaviors.

executor
  ::

    executor(tool, job_order_object, runtimeContext, logger)
      (Process, Dict[Text, Any], RuntimeContext) -> Tuple[Dict[Text, Any], Text]

  An implementation of the top-level workflow execution loop should
  synchronously run a process object to completion and return the
  output object.

versionfunc
  ::

    ()
      () -> Text

  Return version string.

logger_handler
  ::

    logger_handler
      logging.Handler

  Handler object for logging.

The following functions can be set in LoadingContext to override or
augment the listed behaviors.

fetcher_constructor
  ::

    fetcher_constructor(cache, session)
      (Dict[unicode, unicode], requests.sessions.Session) -> Fetcher

  Construct a Fetcher object with the supplied cache and HTTP session.

resolver
  ::

    resolver(document_loader, document)
      (Loader, Union[Text, dict[Text, Any]]) -> Text

  Resolve a relative document identifier to an absolute one that can be fetched.

The following functions can be set in RuntimeContext to override or
augment the listed behaviors.

construct_tool_object
  ::

    construct_tool_object(toolpath_object, loadingContext)
      (MutableMapping[Text, Any], LoadingContext) -> Process

  Hook to construct a Process object (eg CommandLineTool) object from a document.

select_resources
  ::

    selectResources(request)
      (Dict[str, int], RuntimeContext) -> Dict[Text, int]

  Take a resource request and turn it into a concrete resource assignment.

make_fs_access
  ::

    make_fs_access(basedir)
      (Text) -> StdFsAccess

  Return a file system access object.

In addition, when providing custom subclasses of Process objects, you can override the following methods:

CommandLineTool.make_job_runner
  ::

    make_job_runner(RuntimeContext)
      (RuntimeContext) -> Type[JobBase]

  Create and return a job runner object (this implements concrete execution of a command line tool).

Workflow.make_workflow_step
  ::

    make_workflow_step(toolpath_object, pos, loadingContext, parentworkflowProv)
      (Dict[Text, Any], int, LoadingContext, Optional[ProvenanceProfile]) -> WorkflowStep

  Create and return a workflow step object.
