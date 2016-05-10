import json
import urlparse
from schema_salad.ref_resolver import Loader
from rdflib import Graph, plugin, URIRef
from rdflib.serializer import Serializer
from typing import Any, Union, Dict, IO

def makerdf(workflow, wf, ctx):
    # type: (Union[str, unicode], Dict[str,Any], Loader.ContextType) -> Graph
    prefixes = {}
    for k,v in ctx.iteritems():
        if isinstance(v, dict):
            url = v["@id"]
        else:
            url = v
        doc_url, frg = urlparse.urldefrag(url)
        if "/" in frg:
            p, _ = frg.split("/")
            prefixes[p] = u"%s#%s/" % (doc_url, p)

    wf["@context"] = ctx
    g = Graph().parse(data=json.dumps(wf), format='json-ld', location=workflow)

    # Bug in json-ld loader causes @id fields to be added to the graph
    for s,p,o in g.triples((None, URIRef("@id"), None)):
        g.remove((s, p, o))

    for k2,v2 in prefixes.iteritems():
        g.namespace_manager.bind(k2, v2)

    return g

def printrdf(workflow, wf, ctx, sr, stdout):
    # type: (Union[str, unicode], Dict[str, Any], Loader.ContextType, str, IO[Any]) -> None
    stdout.write(makerdf(workflow, wf, ctx).serialize(format=sr))

def lastpart(uri):  # type: (Any) -> str
    uri = str(uri)
    if "/" in uri:
        return uri[uri.rindex("/")+1:]
    else:
        return uri


def dot_with_parameters(g, stdout):  # type: (Graph, IO[Any]) -> None
    qres = g.query(
        """SELECT ?step ?run ?runtype
           WHERE {
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           }""")

    for step, run, runtype in qres:
        stdout.write(u'"%s" [label="%s"]\n' % (lastpart(step), "%s (%s)" % (lastpart(step), lastpart(run))))

    qres = g.query(
        """SELECT ?step ?inp ?source
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:inputs ?inp .
              ?inp cwl:source ?source .
           }""")

    for step, inp, source in qres:
        stdout.write(u'"%s" [shape=box]\n' % (lastpart(inp)))
        stdout.write(u'"%s" -> "%s" [label="%s"]\n' % (lastpart(source), lastpart(inp), ""))
        stdout.write(u'"%s" -> "%s" [label="%s"]\n' % (lastpart(inp), lastpart(step), ""))

    qres = g.query(
        """SELECT ?step ?out
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:outputs ?out .
           }""")

    for step, out in qres:
        stdout.write(u'"%s" [shape=box]\n' % (lastpart(out)))
        stdout.write(u'"%s" -> "%s" [label="%s"]\n' % (lastpart(step), lastpart(out), ""))

    qres = g.query(
        """SELECT ?out ?source
           WHERE {
              ?wf cwl:outputs ?out .
              ?out cwl:source ?source .
           }""")

    for out, source in qres:
        stdout.write(u'"%s" [shape=octagon]\n' % (lastpart(out)))
        stdout.write(u'"%s" -> "%s" [label="%s"]\n' % (lastpart(source), lastpart(out), ""))

    qres = g.query(
        """SELECT ?inp
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf cwl:inputs ?inp .
           }""")

    for (inp,) in qres:
        stdout.write(u'"%s" [shape=octagon]\n' % (lastpart(inp)))

def dot_without_parameters(g, stdout):  # type: (Graph, IO[Any]) -> None
    dotname = {}  # type: Dict[str,str]
    clusternode = {}

    stdout.write("compound=true\n")

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
                stdout.write("}\n")
            if wf in subworkflows:
                if wf not in dotname:
                    dotname[wf] = "cluster_" + lastpart(wf)
                stdout.write(u'subgraph "%s" { label="%s"\n' % (dotname[wf], lastpart(wf)))
                currentwf = wf
                clusternode[wf] = step
            else:
                currentwf = None

        if str(runtype) != "https://w3id.org/cwl/cwl#Workflow":
            stdout.write(u'"%s" [label="%s"]\n' % (dotname[step], urlparse.urldefrag(str(step))[1]))

    if currentwf is not None:
        stdout.write("}\n")

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
        attr = u""
        if srcrun in clusternode:
            attr += u'ltail="%s"' % dotname[srcrun]
            src = clusternode[srcrun]
        if sinkrun in clusternode:
            attr += u' lhead="%s"' % dotname[sinkrun]
            sink = clusternode[sinkrun]
        stdout.write(u'"%s" -> "%s" [%s]\n' % (dotname[src], dotname[sink], attr))


def printdot(workflow, wf, ctx, stdout, include_parameters=False):
    # type: (Union[str, unicode], Dict[str, Any], Loader.ContextType, Any, bool) -> None
    g = makerdf(workflow, wf, ctx)

    stdout.write("digraph {")

    #g.namespace_manager.qname(predicate)

    if include_parameters:
        dot_with_parameters(g, stdout)
    else:
        dot_without_parameters(g, stdout)

    stdout.write("}")
