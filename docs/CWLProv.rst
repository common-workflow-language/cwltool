Provenance capture
------------------

It is possible to capture the full provenance of a workflow execution to 
a folder, including intermediate values:

.. code-block:: sh

    cwltool --provenance revsort-run-1/ tests/wf/revsort.cwl tests/wf/revsort-job.json

Who executed the workflow?
^^^^^^^^^^^^^^^^^^^^^^^^^^

Optional parameters are available to capture information about *who* executed the workflow *where*:

.. code-block:: sh

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
``ORCID`` and ``CWL_FULL_NAME`` to avoid supplying ``--orcid`` 
or ``--full-name`` for every workflow run, 
for instance by augmenting the ``~/.bashrc`` or equivalent:

.. code-block:: sh

    export ORCID=https://orcid.org/0000-0002-1825-0097
    export CWL_FULL_NAME="Stian Soiland-Reyes"

Care should be taken to preserve spaces when setting `--full-name` or `CWL_FULL_NAME`.


CWLProv folder structure
^^^^^^^^^^^^^^^^^^^^^^^^

The CWLProv folder structure under ``revsort-run-1`` is a 
`Research Object <http://www.researchobject.org/>`__
that conforms to the `RO BagIt profile <https://w3id.org/ro/bagit>`__
and contains `PROV <https://www.w3.org/TR/prov-overview/>`__ 
traces detailing the execution of the workflow and its steps.

A rough overview of the CWLProv folder structure:

* ``bagit.txt`` - bag marker for `BagIt <https://tools.ietf.org/html/draft-kunze-bagit-14>`__.
* ``bag-info.txt`` - minimal bag metadata. ``The External-Identifier`` key shows which `arcp <https://tools.ietf.org/id/draft-soilandreyes-arcp-03.html>`__ can be used as base URI within the folder bag.
* ``manifest-*.txt`` - checksums of files under ``data/`` (algorithms subject to change)
* ``tagmanifest-*.txt`` - checksums of the remaining files (algorithms subject to change)
* ``metadata/manifest.json`` - `Research Object manifest <https://w3id.org/bundle/#manifest>`__ as JSON-LD. Types and relates files within bag.
* ``metadata/provenance/primary.cwlprov*`` -  `PROV <https://www.w3.org/TR/prov-overview/>`__ trace of main workflow execution in alternative PROV and RDF formats
* ``data/`` - bag payload, workflow/step input/output data files (content-addressable)
* ``data/32/327fc7aedf4f6b69a42a7c8b808dc5a7aff61376`` - a data item with checksum ``327fc7aedf4f6b69a42a7c8b808dc5a7aff61376`` (checksum algorithm is subject to change)
* ``workflow/packed.cwl`` - The ``cwltool --pack`` standalone version of the executed workflow
* ``workflow/primary-job.json`` - Job input for use with ``packed.cwl`` (references ``data/*``)
* ``snapshot/`` - Direct copies of original files used for execution, but may have broken relative/absolute paths


See the `CWLProv paper <https://doi.org/10.5281/zenodo.1208477>`__ for more details.

Research Object manifest
^^^^^^^^^^^^^^^^^^^^^^^^

The file ``metadata/manifest.json`` follows the structure defined for `Research Object Bundles <https://w3id.org/bundle/#manifest>`_ - but 
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

Note that the `arcp <https://tools.ietf.org/id/draft-soilandreyes-arcp-03.html>`__  base URI will correspond to the UUID of each main workflow run.

Account who launched cwltool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If ``--enable-user-provenance`` was used, the local machine account (e.g. Windows or UNIX user name) who started ``cwltool`` is tracked::

    agent(id:855c6823-bbe7-48a5-be37-b0f07f20c495, [foaf:accountName="stain", prov:type='foaf:OnlineAccount', prov:label="stain"])

It is assumed that the account was under the control of the named person (in PROV terms "actedOnBehalfOf")::

    agent(id:433df002-2584-462a-80b0-cf90b97e6e07, [prov:label="Stian Soiland-Reyes", 
          prov:type='prov:Person', foaf:account='id:8815e39c-9711-4105-bf52-dbc016c8028f'])
    actedOnBehalfOf(id:8815e39c-9711-4105-bf52-dbc016c8028f, id:433df002-2584-462a-80b0-cf90b97e6e07, -)
 
However we do not have an identifier for neither the account or the person, so every ``cwltool`` run will yield new UUIDs. 

With ``--enable-user-provenance`` it is possible to associate the account with a hostname::

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

But we can also expand the ``wf`` identifiers to find that we are talking about 
``arcp://uuid,0e6cb79e-fe70-4807-888c-3a61b9bf232a/workflow/packed.cwl#`` - that is 
the ``main`` workflow in the file ``workflow/packed.cwl`` of the Research Object.

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


