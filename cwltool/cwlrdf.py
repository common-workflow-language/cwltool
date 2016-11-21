import json
import urlparse
from .process import Process
from schema_salad.ref_resolver import Loader, ContextType
from schema_salad.jsonld_context import makerdf
from rdflib import Graph, plugin, URIRef
from rdflib.serializer import Serializer
from typing import Any, Dict, IO, Text, Union

def gather(tool, ctx):  # type: (Process, ContextType) -> Graph
    g = Graph()

    def visitor(t):
        makerdf(t["id"], t, ctx, graph=g)

    tool.visit(visitor)
    return g

def printrdf(wf, ctx, sr, stdout):
    # type: (Process, ContextType, Text, IO[Any]) -> None
    stdout.write(gather(wf, ctx).serialize(format=sr))

def lastpart(uri):  # type: (Any) -> Text
    uri = Text(uri)
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
    dotname = {}  # type: Dict[Text,Text]
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

        if Text(runtype) != "https://w3id.org/cwl/cwl#Workflow":
            stdout.write(u'"%s" [label="%s"]\n' % (dotname[step], urlparse.urldefrag(Text(step))[1]))

    if currentwf is not None:
        stdout.write("}\n")

    qres = g.query(
        """SELECT DISTINCT ?src ?sink ?srcrun ?sinkrun
           WHERE {
              ?wf1 Workflow:steps ?src .
              ?wf2 Workflow:steps ?sink .
              ?src cwl:out ?out .
              ?inp cwl:source ?out .
              ?sink cwl:in ?inp .
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


def printdot(wf, ctx, stdout, include_parameters=False):
    # type: (Process, ContextType, Any, bool) -> None
    g = gather(wf, ctx)

    stdout.write("digraph {")

    #g.namespace_manager.qname(predicate)

    if include_parameters:
        dot_with_parameters(g, stdout)
    else:
        dot_without_parameters(g, stdout)

    stdout.write("}")
