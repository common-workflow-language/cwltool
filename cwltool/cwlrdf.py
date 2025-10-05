"""RDF output."""

from typing import IO, Any

from rdflib import Graph
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
    return str(rdf, "utf-8")


def lastpart(uri: Any) -> str:
    uri2 = str(uri)
    if "/" in uri2:
        return uri2[uri2.rindex("/") + 1 :]
    return uri2


def printdot(
    wf: Process,
    ctx: ContextType,
    stdout: IO[str],
) -> None:
    cwl_viewer: CWLViewer = CWLViewer(printrdf(wf, ctx, "n3"))
    stdout.write(cwl_viewer.dot().replace(f"{wf.metadata['id']}#", ""))
