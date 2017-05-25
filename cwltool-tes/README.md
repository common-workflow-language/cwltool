# GA4GH CWL Task Execution 

___cwltool-tes___ submits your tasks to a TES server. Task submission is parallelized when possible.

[Funnel](https://ohsu-comp-bio.github.io/funnel) is an implementation of the [GA4GH task execution API](https://github.com/ga4gh/task-execution-schemas). It runs your dockerized tasks on slurm, htcondor, google compute engine, etc.

It 

## Requirements

* Python 2.7

* [Docker](https://docs.docker.com/)

* [Funnel](https://ohsu-comp-bio.github.io/funnel)

## Quickstart

* Start the task server

```
funnel server
```

* Run your CWL tool/workflow

```
TMPDIR=./ ./cwltool-tes --tes http://localhost:8000 tests/hashsplitter-workflow.cwl.yml --input tests/resources/test.txt
```

## Install

To install from source:

```
python setup.py install
```
