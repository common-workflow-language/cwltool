import json
import urlparse
from rdflib import Graph, plugin, URIRef
from rdflib.serializer import Serializer

def makerdf(workflow, wf, ctx):
    prefixes = {}
    for k,v in ctx.iteritems():
        if isinstance(v, dict):
            v = v["@id"]
        doc_url, frg = urlparse.urldefrag(v)
        if "/" in frg:
            p, _ = frg.split("/")
            prefixes[p] = "%s#%s/" % (doc_url, p)

    wf["@context"] = ctx
    g = Graph().parse(data=json.dumps(wf), format='json-ld', location=workflow)

    # Bug in json-ld loader causes @id fields to be added to the graph
    for s,p,o in g.triples((None, URIRef("@id"), None)):
        g.remove((s, p, o))

    for k,v in prefixes.iteritems():
        g.namespace_manager.bind(k, v)

    return g

def printrdf(workflow, wf, ctx, sr):
    print(makerdf(workflow, wf, ctx).serialize(format=sr))

def lastpart(uri):
    uri = str(uri)
    if "/" in uri:
        return uri[uri.rindex("/")+1:]
    else:
        return uri


def dot_with_parameters(g):
    qres = g.query(
        """SELECT ?step ?run ?runtype
           WHERE {
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           }""")

    for step, run, runtype in qres:
        print '"%s" [label="%s"]' % (lastpart(step), "%s (%s)" % (lastpart(step), lastpart(run)))

    qres = g.query(
        """SELECT ?step ?inp ?source
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:inputs ?inp .
              ?inp cwl:source ?source .
           }""")

    for step, inp, source in qres:
        print '"%s" [shape=box]' % (lastpart(inp))
        print '"%s" -> "%s" [label="%s"]' % (lastpart(source), lastpart(inp), "")
        print '"%s" -> "%s" [label="%s"]' % (lastpart(inp), lastpart(step), "")

    qres = g.query(
        """SELECT ?step ?out
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:outputs ?out .
           }""")

    for step, out in qres:
        print '"%s" [shape=box]' % (lastpart(out))
        print '"%s" -> "%s" [label="%s"]' % (lastpart(step), lastpart(out), "")

    qres = g.query(
        """SELECT ?out ?source
           WHERE {
              ?wf cwl:outputs ?out .
              ?out cwl:source ?source .
           }""")

    for out, source in qres:
        print '"%s" [shape=octagon]' % (lastpart(out))
        print '"%s" -> "%s" [label="%s"]' % (lastpart(source), lastpart(out), "")

    qres = g.query(
        """SELECT ?inp
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf cwl:inputs ?inp .
           }""")

    for (inp,) in qres:
        print '"%s" [shape=octagon]' % (lastpart(inp))

def dot_without_parameters(g):
    dotname = {}
    clusternode = {}

    print "compound=true"

    subworkflows = set()
    qres = g.query(
        """SELECT ?run
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf Workflow:steps ?step .
              ?step cwl:run ?run .
              ?run rdf:type cwl:Workflow .
           } ORDER BY ?wf""")
    for (run,) in qres:
        subworkflows.add(run)

    qres = g.query(
        """SELECT ?wf ?step ?run ?runtype
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf Workflow:steps ?step .
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           } ORDER BY ?wf""")

    currentwf = None
    for wf, step, run, runtype in qres:
        if step not in dotname:
            dotname[step] = lastpart(step)

        if wf != currentwf:
            if currentwf is not None:
                print "}"
            if wf in subworkflows:
                if wf not in dotname:
                    dotname[wf] = "cluster_" + lastpart(wf)
                print 'subgraph "%s" { label="%s"' % (dotname[wf], lastpart(wf))
                currentwf = wf
                clusternode[wf] = step
            else:
                currentwf = None

        if str(runtype) != "https://w3id.org/cwl/cwl#Workflow":
            print '"%s" [label="%s"]' % (dotname[step], urlparse.urldefrag(str(step))[1])

    if currentwf is not None:
        print "}\n"

    qres = g.query(
        """SELECT DISTINCT ?src ?sink ?srcrun ?sinkrun
           WHERE {
              ?wf1 Workflow:steps ?src .
              ?wf2 Workflow:steps ?sink .
              ?src cwl:outputs ?out .
              ?inp cwl:source ?out .
              ?sink cwl:inputs ?inp .
              ?src cwl:run ?srcrun .
              ?sink cwl:run ?sinkrun .
           }""")

    for src, sink, srcrun, sinkrun in qres:
        attr = ""
        if srcrun in clusternode:
            attr += 'ltail="%s"' % dotname[srcrun]
            src = clusternode[srcrun]
        if sinkrun in clusternode:
            attr += ' lhead="%s"' % dotname[sinkrun]
            sink = clusternode[sinkrun]
        print '"%s" -> "%s" [%s]' % (dotname[src], dotname[sink], attr)


def printdot(workflow, wf, ctx, include_parameters=False):
    g = makerdf(workflow, wf, ctx)

    print "digraph {"

    #g.namespace_manager.qname(predicate)

    if include_parameters:
        dot_with_parmeters(g)
    else:
        dot_without_parameters(g)

    print "}"
