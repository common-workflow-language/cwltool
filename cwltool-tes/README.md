# GA4GH CWL Task Execution 

## Quickstart
 
* Install Docker
* Install Funnel

```
go get github.com/ohsu-comp-bio/funnel
```

* Start the task server

```
$GOPATH/bin/funnel server
```

* Run your CWL tool/workflow

```
TMPDIR=./ ./cwltool-tes --tes http://localhost:8000 tests/hashsplitter-md5.cwl.yml --input tests/resources/test.txt
```

## Resources

* [GA4GH Task Execution Schema](https://github.com/ga4gh/task-execution-schemas)
* [Funnel](https://github.com/ohsu-comp-bio/funnel)
