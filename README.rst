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


Provenance capture
------------------

It is possible to capture the full provenance of a workflow execution to 
a folder, including intermediate values:

    cwltool --provenance revsort-run-1/ tests/wf/revsort.cwl tests/wf/revsort-job.json

Who executed the workflow?
^^^^^^^^^^^^^^^^^^^^^^^^^^

Optional parameters are available to capture information about *who* executed the workflow *where*:

    cwltool --orcid https://orcid.org/0000-0002-1825-0097 \
      --full-name "Alice W Land" \
      --enable-user-provenance --enable-host-provenance \
      --provenance revsort-run-1/ \
      tests/wf/revsort.cwl tests/wf/revsort-job.json

These parameters are opt-in as they track person-identifiable information. 
The options ``--enable-user-provenance`` and ``--enable-host-provenance`` will
pick up account/machine info from where ``cwltool`` is executed (e.g. 
UNIX username).  This may get the full name of the user wrong, in which case 
``--full-name`` can be supplied.

For consistent tracking it is recommended to apply for 
an `ORCID <https://orcid.org/>`__ identifier and provide it as above, 
since ``--enable-user-provenance --enable-host-provenance`` 
are only able to identify the local machine account.

It is possible to set the shell environment variables
`ORCID` and `CWL_FULL_NAME` to avoid supplying ``--orcid`` 
or `--full-name` for every workflow run, 
for instance by augmenting the ``~/.bashrc`` or equivalent:

    export ORCID=https://orcid.org/0000-0002-1825-0097
    export CWL_FULL_NAME="Stian Soiland-Reyes"

Care should be taken to preserve spaces when setting `--full-name` or `CWL_FULL_NAME`.


CWLProv folder structure
^^^^^^^^^^^^^^^^^^^^^^^^

The CWLProv folder structure under revsort-run-1 is a 
`Research Object <http://www.researchobject.org/>`__
that conforms to the `RO BagIt profile <https://w3id.org/ro/bagit>`__
and contains `PROV <https://www.w3.org/TR/prov-overview/>`__ 
traces detailing the execution of the workflow and its steps.


A rough overview of the CWLProv folder structure:

* ``bagit.txt`` - bag marker for `BagIt <https://tools.ietf.org/html/draft-kunze-bagit-14>`__.
* ``bag-info.txt`` - minimal bag metadata. ``The External-Identifier`` key shows which `arcp <https://tools.ietf.org/id/draft-soilandreyes-arcp-03.html>`__ can be used as base URI within the folder bag.
* ``manifest-*.txt`` - checksums of files under data/ (algorithms subject to change)
* ``tagmanifest-*.txt`` - checksums of the remaining files (algorithms subject to change)
* ``metadata/manifest.json`` - `Research Object manifest <https://w3id.org/bundle/#manifest>`__ as JSON-LD. Types and relates files within bag.
* ``metadata/provenance/primary.cwlprov*`` -  `PROV <https://www.w3.org/TR/prov-overview/>`__ trace of main workflow execution in alternative PROV and RDF formats
* ``data/`` - bag payload, workflow/step input/output data files (content-addressable)
* ``data/32/327fc7aedf4f6b69a42a7c8b808dc5a7aff61376`` - a data item with checksum ``327fc7aedf4f6b69a42a7c8b808dc5a7aff61376`` (checksum algorithm is subject to change)
* ``workflow/packed.cwl`` - The ``cwltool --pack`` standalone version of the executed workflow
* ``workflow/primary-job.json`` - Job input for use with packed.cwl (references ``data/*``)
* ``snapshot/`` - Direct copies of original files used for execution, but may have broken relative/absolute paths


See the `CWLProv paper <https://doi.org/10.5281/zenodo.1208477>`__ for more details.

Research Object manifest
^^^^^^^^^^^^^^^^^^^^^^^^

The file ``metadata/manifest.json`` follows the structure defined for `Research Object Bundles <https://w3id.org/bundle/#manifest>` - but 
note that ``.ro/`` is instead called ``metadata/`` as this conforms to the `RO BagIt profile <https://w3id.org/ro/bagit>`__.

Some of the keys of the CWLProv manifest are explained below::

    "@context": [
        {
            "@base": "arcp://uuid,67f38794-d24a-435f-bd4a-0242a56a581b/metadata/"
        },
        "https://w3id.org/bundle/context"
    ]

This `JSON-LD context <https://json-ld.org/>`__ enables consumers to alternatively consume the JSON file as Linked Data with absolute identifiers. 
The key for that is the ``@base`` which means URIs within this JSON file are relative to the ``metadata/`` folder 
within this Research Object bag, and the external JSON-LD .

Output from ``cwltool`` should follow the JSON structure shown beyond; however interested consumer may alternatively parse it as JSON-LD with a RDF triple store like `Apache Jena <https://jena.apache.org/download/>`__ for further querying.

The manifest lists which software version created the Research Object - we will hear more from this UUID later::

    "createdBy": {
        "uri": "urn:uuid:7c9d9e88-666b-4977-85f4-c02da08a942d",
        "name": "cwltool 1.0.20180416145054"
    }

Secondly the manifest lists the person who "authored the run" - that is put the workflow and inputs together with cwltool::

    "authoredBy": {
        "orcid": "https://orcid.org/0000-0002-1825-0097",
        "name": "Stian Soiland-Reyes"
    }

Note that the author of the workflow run may differ from the author of the workflow definition.

The list of aggregates are the main resources that this Research Object transports::

    "aggregates": [
        {
            "uri": "urn:hash::sha1:53870991af88a6d678cbeed3255bb65993c52925",
            ...
        }, 
        { "provenance/primary.cwlprov.xml",
           ...
        },
        {
            "uri": "../workflow/packed.cwl",
            "createdBy": {
                "uri": "urn:uuid:7c9d9e88-666b-4977-85f4-c02da08a942d",
                "name": "cwltool 1.0.20180416145054"
            },
            "conformsTo": "https://w3id.org/cwl/",
            "mediatype": "text/x+yaml; charset=\"UTF-8\"",
            "createdOn": "2018-04-16T18:27:09.513824"
        },
        {
            "uri": "../snapshot/hello-workflow.cwl",
            "conformsTo": "https://w3id.org/cwl/",
            "mediatype": "text/x+yaml; charset=\"UTF-8\"",
            "createdOn": "2018-04-04T13:29:55.717707"
        }
        

Beyond being a listing of file names and identifiers, this also lists formats and light-weight provenance. We note that the
CWL file is marked to conform to the https://w3id.org/cwl/ CWL specification.

Some of the files like ``packed.cwl`` have been created by cwltool as part of the run, while others have been created before the run "outside".
Note that ``cwltool`` is currently unable to extract the original authors and contributors of the original files, this is planned for future versions.

Under ``annotations`` we see that the main point of this whole research object (``/`` aka ``arcp://uuid,67f38794-d24a-435f-bd4a-0242a56a581b/``) 
is to describe something called ``urn:uuid:67f38794-d24a-435f-bd4a-0242a56a581b``::

    "annotations": [
        {       
            "about": "urn:uuid:67f38794-d24a-435f-bd4a-0242a56a581b",
            "content": "/",
            "oa:motivatedBy": {
                "@id": "oa:describing"
            }
        },


We will later see that this is the UUID for the workflow run. A workflow run is an *activity*, 
something that happens - it can't be directly saved to a file. However it can be *described* in 
different ways, in this case as CWLProv provenance::


           {
            "about": "urn:uuid:67f38794-d24a-435f-bd4a-0242a56a581b",
            "content": [
                "provenance/primary.cwlprov.xml",
                "provenance/primary.cwlprov.nt",
                "provenance/primary.cwlprov.ttl",
                "provenance/primary.cwlprov.provn",
                "provenance/primary.cwlprov.jsonld",
                "provenance/primary.cwlprov.json"
            ],
            "oa:motivatedBy": {
                "@id": "http://www.w3.org/ns/prov#has_provenance"
            }

Finally the research object wants to highlight the workflow file::

        {
            "about": "workflow/packed.cwl",
            "oa:motivatedBy": {
                "@id": "oa:highlighting"
            }
        },


And links the run ID ``67f38794..`` to the ```primary-job.json`` and ``packed.cwl``::

        {
            "about": "urn:uuid:67f38794-d24a-435f-bd4a-0242a56a581b",
            "content": [
                "workflow/packed.cwl",
                "workflow/primary-job.json"
            ],
            "oa:motivatedBy": {
                "@id": "oa:linking"
            }
        }

Note: ``oa:motivatedBy`` in CWLProv are subject to change.


PROV profile
^^^^^^^^^^^^

The underlying model and information of the `PROV <https://www.w3.org/TR/prov-overview/>`__
files under ``metadata/provenance`` is the same, but is made available in multiple 
serialization formats:

* primary.cwlprov.provn -- `PROV-N <https://www.w3.org/TR/prov-n/>`__ Textual Provenance Notation 
* primary.cwlprov.xml -- `PROV-XML <https://www.w3.org/TR/prov-xml/>`__
* primary.cwlprov.json -- `PROV-JSON <https://www.w3.org/Submission/prov-json/>`__
* primary.cwlprov.jsonld -- `PROV-O <https://www.w3.org/TR/prov-o/>`__ as `JSON-LD <https://json-ld.org/>`__ (``@context`` subject to change)
* primary.cwlprov.ttl -- `PROV-O <https://www.w3.org/TR/prov-o/>`__ as `RDF Turtle <https://www.w3.org/TR/turtle/>`__
* primary.cwlprov.nt -- `PROV-O <https://www.w3.org/TR/prov-o/>`__ as `RDF N-Triples <https://www.w3.org/TR/n-triples/>`__

The below extracts use the PROV-N syntax for brevity.

CWLPROV namespaces
^^^^^^^^^^^^^^^^^^

Note that the identifiers must be expanded with the defined ``prefix``-es when comparing across serializations.
These set which vocabularies ("namespaces") are used by the CWLProv statements::

    prefix data <urn:hash::sha1:>
    prefix input <arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/workflow/primary-job.json#>
    prefix cwlprov <https://w3id.org/cwl/prov#>
    prefix wfprov <http://purl.org/wf4ever/wfprov#>
    prefix sha256 <nih:sha-256;>
    prefix schema <http://schema.org/>
    prefix wfdesc <http://purl.org/wf4ever/wfdesc#>
    prefix orcid <https://orcid.org/>
    prefix researchobject <arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/>
    prefix id <urn:uuid:>
    prefix wf <arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/workflow/packed.cwl#>
    prefix foaf <http://xmlns.com/foaf/0.1/>

Note that the `arcp <https://tools.ietf.org/id/draft-soilandreyes-arcp-03.html>`__  base URI will correspond to the UUID of each master workflow run.

Account who launched cwltool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If `--enable-user-provenance` was used, the local machine acccount (e.g. Windows or UNIX user name) who started ``cwltool`` is tracked::

    agent(id:855c6823-bbe7-48a5-be37-b0f07f20c495, [foaf:accountName="stain", prov:type='foaf:OnlineAccount', prov:label="stain"])

It is assumed that the account was under the control of the named person (in PROV terms "actedOnBehalfOf")::

    agent(id:433df002-2584-462a-80b0-cf90b97e6e07, [prov:label="Stian Soiland-Reyes", 
          prov:type='prov:Person', foaf:account='id:8815e39c-9711-4105-bf52-dbc016c8028f'])
    actedOnBehalfOf(id:8815e39c-9711-4105-bf52-dbc016c8028f, id:433df002-2584-462a-80b0-cf90b97e6e07, -)
 
However we do not have an identifier for neither the account or the person, so every ``cwltool`` run will yield new UUIDs. 

With --enable-user-provenance it is possible to associate the account with a hostname::

    agent(id:855c6823-bbe7-48a5-be37-b0f07f20c495, [cwlprov:hostname="biggie", prov:type='foaf:OnlineAccount', prov:location="biggie"])

Note that the hostname is often non-global or variable (e.g. on cloud instances or virtual machines), 
and thus may be unreliable when considering ``cwltool`` executions on multiple hosts.

If the ``--orcid`` parameter or ``ORCID`` shell variable is included, then the person associated 
with the local machine account is uniquely identified, no matter where the workflow was executed::

    agent(orcid:0000-0002-1825-0097, [prov:type='prov:Person', prov:label="Stian Soiland-Reyes", 
       foaf:account='id:855c6823-bbe7-48a5-be37-b0f07f20c495'])

    actedOnBehalfOf(id:855c6823-bbe7-48a5-be37-b0f07f20c495', orcid:0000-0002-1825-0097, -)

The running of `cwltool` itself makes it the workflow engine. It is the machine account who launched the cwltool (not necessarily the person behind it)::

    agent(id:7c9d9e88-666b-4977-85f4-c02da08a942d, [prov:type='prov:SoftwareAgent', prov:type='wfprov:WorkflowEngine', prov:label="cwltool 1.0.20180416145054"])
    wasStartedBy(id:855c6823-bbe7-48a5-be37-b0f07f20c495, -, id:9c3d4d1f-473d-468f-a6f2-1ef4de571a7f, 2018-04-16T18:27:09.428090)

Starting a workflow
^^^^^^^^^^^^^^^^^^^

The main job of the cwltool execution is to run a workflow, here the activity for ``workflow/packed.cwl#main``::

  activity(id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.428165, -, [prov:type='wfprov:WorkflowRun', prov:label="Run of workflow/packed.cwl#main"])
  wasStartedBy(id:67f38794-d24a-435f-bd4a-0242a56a581b, -, id:7c9d9e88-666b-4977-85f4-c02da08a942d, 2018-04-16T18:27:09.428285)

Now what is that workflow again? Well a tiny bit of prospective provenance is included::

  entity(wf:main, [prov:type='prov:Plan', prov:type='wfdesc:Workflow', prov:label="Prospective provenance"])
  entity(wf:main, [prov:label="Prospective provenance", wfdesc:hasSubProcess='wf:main/step0'])
  entity(wf:main/step0, [prov:type='wfdesc:Process', prov:type='prov:Plan'])

But we can also expand the `wf` identifiers to find that we are talking about 
``arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/workflow/packed.cwl#`` - that is 
the ``main`` workflow in the file `workflow/packed.cwl` of the Research Object.

Running workflow steps
^^^^^^^^^^^^^^^^^^^^^^

A workflow will contain some steps, each execution of these are again nested activities::

  activity(id:6c7c04ea-dcc8-40d2-92a4-7705f7286756, -, -, [prov:type='wfprov:ProcessRun', prov:label="Run of workflow/packed.cwl#main"])
  wasStartedBy(id:6c7c04ea-dcc8-40d2-92a4-7705f7286756, -, id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.430883)
  activity(id:a583b025-9a16-49ce-8515-f3249eb2aacf, -, -, [prov:type='wfprov:ProcessRun', prov:label="Run of workflow/packed.cwl#main/step0"])
  wasAssociatedWith(id:a583b025-9a16-49ce-8515-f3249eb2aacf, -, wf:main/step0)

Again we see the link back to the workflow plan, the workflow execution of ``#main/step0`` in this case. 
Note that depending on scattering etc there might 
be multiple activities for a single step in the workflow definition. 

Data inputs (usage)
^^^^^^^^^^^^^^^^^^^

This activities uses some data at the input ``message``::

  activity(id:a583b025-9a16-49ce-8515-f3249eb2aacf, -, -, [prov:type='wfprov:ProcessRun', prov:label="Run of workflow/packed.cwl#main/step0"])
  used(id:a583b025-9a16-49ce-8515-f3249eb2aacf, data:53870991af88a6d678cbeed3255bb65993c52925, 2018-04-16T18:27:09.433743, [prov:role='wf:main/step0/message'])

Data files within a workflow execution are identified using ``urn:hash::sha1:`` URIs derived from their sha1 checksum (checksum algorithm and prefix subject to change)::

    entity(data:53870991af88a6d678cbeed3255bb65993c52925, [prov:type='wfprov:Artifact', prov:value="Hei7"])

Small values (typically those provided on the command line may be present as `prov:value`. The corresponding 
``data/`` file within the Research Object has a content-addressable filename based on the checksum; but it is also 
possible to look up this independent from the corresponding ``metadata/manifest.json`` aggregation::

    "aggregates": [
        {
            "uri": "urn:hash::sha1:53870991af88a6d678cbeed3255bb65993c52925",
            "bundledAs": {
                "uri": "arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/data/53/53870991af88a6d678cbeed3255bb65993c52925",
                "folder": "/data/53/",
                "filename": "53870991af88a6d678cbeed3255bb65993c52925"
            }
        },

Data outputs (generation)
^^^^^^^^^^^^^^^^^^^^^^^^^

Similarly a step typically generates some data, here ``response``::

    activity(id:a583b025-9a16-49ce-8515-f3249eb2aacf, -, -, [prov:type='wfprov:ProcessRun', prov:label="Run of workflow/packed.cwl#main/step0"])
    wasGeneratedBy(data:53870991af88a6d678cbeed3255bb65993c52925, id:a583b025-9a16-49ce-8515-f3249eb2aacf, 2018-04-16T18:27:09.438236, [prov:role='wf:main/step0/response'])
 
In the hello world example this is interesting because it is the same data output as-is, but typically the outputs will each have different checksums (and thus different identifiers).

The step is ended::

   wasEndedBy(id:a583b025-9a16-49ce-8515-f3249eb2aacf, -, id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.438482)


In this case the step output is also a workflow output ``response``, so the data is also generated by the workflow activity::

  activity(id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.428165, -, [prov:type='wfprov:WorkflowRun', prov:label="Run of workflow/packed.cwl#main"])  
  wasGeneratedBy(data:53870991af88a6d678cbeed3255bb65993c52925, id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.439323, [prov:role='wf:main/response'])

Ending the workflow
^^^^^^^^^^^^^^^^^^^
 
Finally the overall workflow ``#main`` also ends::

  activity(id:67f38794-d24a-435f-bd4a-0242a56a581b, 2018-04-16T18:27:09.428165, -, [prov:type='wfprov:WorkflowRun', prov:label="Run of workflow/packed.cwl#main"])
  agent(id:7c9d9e88-666b-4977-85f4-c02da08a942d, [prov:type='prov:SoftwareAgent', prov:type='wfprov:WorkflowEngine', prov:label="cwltool 1.0.20180416145054"])
  wasEndedBy(id:67f38794-d24a-435f-bd4a-0242a56a581b, -, id:7c9d9e88-666b-4977-85f4-c02da08a942d, 2018-04-16T18:27:09.445785)

Note that the end of the outer ``cwltool`` activity is not recorded, as cwltool is still running at the point of writing out this provenance.

Currently the provenance trace do not distinguish executions within nested workflows; it is planned that these will be tracked in separate files under ``metadata/provenance/``.



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
