import urllib
from codecs import StreamWriter
from typing import IO, Any, Dict, Iterator, Optional, TextIO, Union, cast

from rdflib import Graph
from rdflib.query import ResultRow
from ruamel.yaml.comments import CommentedMap
from schema_salad.jsonld_context import makerdf
from schema_salad.utils import ContextType

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
    return rdf.decode("utf-8")


def lastpart(uri: Any) -> str:
    uri2 = str(uri)
    if "/" in uri2:
        return uri2[uri2.rindex("/") + 1 :]
    return uri2


def dot_with_parameters(g: Graph, stdout: Union[TextIO, StreamWriter]) -> None:
    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?step ?run ?runtype
           WHERE {
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           }"""
        ),
    )  # ResultRow because the query is of type SELECT

    for step, run, _ in qres:
        stdout.write(
            '"%s" [label="%s"]\n' % (lastpart(step), f"{lastpart(step)} ({lastpart(run)})")
        )

    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?step ?inp ?source
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:inputs ?inp .
              ?inp cwl:source ?source .
           }"""
        ),
    )  # ResultRow because the query is of type SELECT

    for step, inp, source in qres:
        stdout.write('"%s" [shape=box]\n' % (lastpart(inp)))
        stdout.write('"{}" -> "{}" [label="{}"]\n'.format(lastpart(source), lastpart(inp), ""))
        stdout.write('"{}" -> "{}" [label="{}"]\n'.format(lastpart(inp), lastpart(step), ""))

    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?step ?out
           WHERE {
              ?wf Workflow:steps ?step .
              ?step cwl:outputs ?out .
           }"""
        ),
    )  # ResultRow because the query is of type SELECT

    for step, out in qres:
        stdout.write('"%s" [shape=box]\n' % (lastpart(out)))
        stdout.write('"{}" -> "{}" [label="{}"]\n'.format(lastpart(step), lastpart(out), ""))

    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?out ?source
           WHERE {
              ?wf cwl:outputs ?out .
              ?out cwl:source ?source .
           }"""
        ),
    )  # ResultRow because the query is of type SELECT

    for out, source in qres:
        stdout.write('"%s" [shape=octagon]\n' % (lastpart(out)))
        stdout.write('"{}" -> "{}" [label="{}"]\n'.format(lastpart(source), lastpart(out), ""))

    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?inp
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf cwl:inputs ?inp .
           }"""
        ),
    )  # ResultRow because the query is of type SELECT

    for (inp,) in qres:
        stdout.write('"%s" [shape=octagon]\n' % (lastpart(inp)))


def dot_without_parameters(g: Graph, stdout: Union[TextIO, StreamWriter]) -> None:
    dotname: Dict[str, str] = {}
    clusternode = {}

    stdout.write("compound=true\n")

    subworkflows = set()
    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?run
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf Workflow:steps ?step .
              ?step cwl:run ?run .
              ?run rdf:type cwl:Workflow .
           } ORDER BY ?wf"""
        ),
    )  # ResultRow because the query is of type SELECT
    for (run,) in qres:
        subworkflows.add(run)

    qres = cast(
        Iterator[ResultRow],
        g.query(
            """SELECT ?wf ?step ?run ?runtype
           WHERE {
              ?wf rdf:type cwl:Workflow .
              ?wf Workflow:steps ?step .
              ?step cwl:run ?run .
              ?run rdf:type ?runtype .
           } ORDER BY ?wf"""
        ),
    )  # ResultRow because the query is of type SELECT

    currentwf: Optional[str] = None
    for wf, step, _run, runtype in qres:
        if step not in dotname:
            dotname[step] = lastpart(step)

        if wf != currentwf:
            if currentwf is not None:
                stdout.write("}\n")
            if wf in subworkflows:
                if wf not in dotname:
                    dotname[wf] = "cluster_" + lastpart(wf)
                stdout.write(f'subgraph "{dotname[wf]}" {{ label="{lastpart(wf)}"\n')  # noqa: B907
                currentwf = wf
                clusternode[wf] = step
            else:
                currentwf = None

        if str(runtype) != "https://w3id.org/cwl/cwl#Workflow":
            stdout.write(
                '"%s" [label="%s"]\n' % (dotname[step], urllib.parse.urldefrag(str(step))[1])
            )

    if currentwf is not None:
        stdout.write("}\n")

    qres = cast(
        Iterator[ResultRow],
        g.query(
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
        ),
    )  # ResultRow because the query is of type SELECT

    for src, sink, srcrun, sinkrun in qres:
        attr = ""
        if srcrun in clusternode:
            attr += 'ltail="%s"' % dotname[srcrun]
            src = clusternode[srcrun]
        if sinkrun in clusternode:
            attr += ' lhead="%s"' % dotname[sinkrun]
            sink = clusternode[sinkrun]
        stdout.write(f'"{dotname[src]}" -> "{dotname[sink]}" [{attr}]\n')  # noqa: B907


def printdot(
    wf: Process,
    ctx: ContextType,
    stdout: IO[str],
) -> None:
    cwl_viewer: CWLViewer = CWLViewer(printrdf(wf, ctx, "n3"))
    stdout.write(cwl_viewer.dot().replace(f"{wf.metadata['id']}#", ""))
