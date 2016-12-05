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

Import as a module
----------------

Add::

  import cwltool

to your script.

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
