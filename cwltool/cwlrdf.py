import urllib
from codecs import StreamWriter
from typing import Any, Dict, Optional, TextIO, Union, cast

from rdflib import Graph
from ruamel.yaml.comments import CommentedMap
from schema_salad.jsonld_context import makerdf
from schema_salad.ref_resolver import ContextType

from .cwlviewer import CWLViewer
from .process import Process


def gather(tool: Process, ctx: ContextType) -> Graph:
    g = Graph()

    def visitor(t: CommentedMap) -> None:
        makerdf(t["id"], t, ctx, graph=g)

    tool.visit(visitor)
    return g


def printrdf(wflow: Process, ctx: ContextType, style: str) -> str:
    """Serialize the CWL document into a string, ready for printing."""
    rdf = gather(wflow, ctx).serialize(format=style, encoding="utf-8")
    if not rdf:
        return ""
    return cast(str, rdf.decode("utf-8"))


def lastpart(uri: Any) -> str:
    uri2 = str(uri)
    if "/" in uri2:
        return uri2[uri2.rindex("/") + 1 :]
    return uri2


def dot_with_parameters(g: Graph, stdout: Union[TextIO, StreamWriter]) -> None:
    qres = g.query(
        """SELECT ?step ?run ?runtype
           WHERE {
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           }"""
    )

    for step, run, _ in qres:
        stdout.write(
            u'"%s" [label="%s"]\n'
            % (lastpart(step), "%s (%s)" % (lastpart(step), lastpart(run)))
        )

    qres = g.query(
        """SELECT ?step ?inp ?source
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:inputs ?inp .
              ?inp cwl:source ?source .
           }"""
    )

    for step, inp, source in qres:
        stdout.write(u'"%s" [shape=box]\n' % (lastpart(inp)))
        stdout.write(
            u'"%s" -> "%s" [label="%s"]\n' % (lastpart(source), lastpart(inp), "")
        )
        stdout.write(
            u'"%s" -> "%s" [label="%s"]\n' % (lastpart(inp), lastpart(step), "")
        )

    qres = g.query(
        """SELECT ?step ?out
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:outputs ?out .
           }"""
    )

    for step, out in qres:
        stdout.write(u'"%s" [shape=box]\n' % (lastpart(out)))
        stdout.write(
            u'"%s" -> "%s" [label="%s"]\n' % (lastpart(step), lastpart(out), "")
        )

    qres = g.query(
        """SELECT ?out ?source
           WHERE {
              ?wf cwl:outputs ?out .
              ?out cwl:source ?source .
           }"""
    )

    for out, source in qres:
        stdout.write(u'"%s" [shape=octagon]\n' % (lastpart(out)))
        stdout.write(
            u'"%s" -> "%s" [label="%s"]\n' % (lastpart(source), lastpart(out), "")
        )

    qres = g.query(
        """SELECT ?inp
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf cwl:inputs ?inp .
           }"""
    )

    for (inp,) in qres:
        stdout.write(u'"%s" [shape=octagon]\n' % (lastpart(inp)))


def dot_without_parameters(g: Graph, stdout: Union[TextIO, StreamWriter]) -> None:
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
           } ORDER BY ?wf"""
    )
    for (run,) in qres:
        subworkflows.add(run)

    qres = g.query(
        """SELECT ?wf ?step ?run ?runtype
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf Workflow:steps ?step .
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           } ORDER BY ?wf"""
    )

    currentwf = None  # type: Optional[str]
    for wf, step, _run, runtype in qres:
        if step not in dotname:
            dotname[step] = lastpart(step)

        if wf != currentwf:
            if currentwf is not None:
                stdout.write("}\n")
            if wf in subworkflows:
                if wf not in dotname:
                    dotname[wf] = "cluster_" + lastpart(wf)
                stdout.write(
                    u'subgraph "%s" { label="%s"\n' % (dotname[wf], lastpart(wf))
                )
                currentwf = wf
                clusternode[wf] = step
            else:
                currentwf = None

        if str(runtype) != "https://w3id.org/cwl/cwl#Workflow":
            stdout.write(
                u'"%s" [label="%s"]\n'
                % (dotname[step], urllib.parse.urldefrag(str(step))[1])
            )

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
           }"""
    )

    for src, sink, srcrun, sinkrun in qres:
        attr = ""
        if srcrun in clusternode:
            attr += u'ltail="%s"' % dotname[srcrun]
            src = clusternode[srcrun]
        if sinkrun in clusternode:
            attr += u' lhead="%s"' % dotname[sinkrun]
            sink = clusternode[sinkrun]
        stdout.write(u'"%s" -> "%s" [%s]\n' % (dotname[src], dotname[sink], attr))


def printdot(
    wf: Process,
    ctx: ContextType,
    stdout: Union[TextIO, StreamWriter],
) -> None:
    cwl_viewer = CWLViewer(printrdf(wf, ctx, "n3"))  # type: CWLViewer
    stdout.write(cwl_viewer.dot())
