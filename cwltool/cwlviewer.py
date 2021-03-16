"""Visualize a CWL workflow."""
import os
from urllib.parse import urlparse

import pydot  # type: ignore
import rdflib


class CWLViewer:
    """Produce similar images with the https://github.com/common-workflow-language/cwlviewer."""

    _queries_dir = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "rdfqueries"
    )
    _get_inner_edges_query_path = os.path.join(_queries_dir, "get_inner_edges.sparql")
    _get_input_edges_query_path = os.path.join(_queries_dir, "get_input_edges.sparql")
    _get_output_edges_query_path = os.path.join(_queries_dir, "get_output_edges.sparql")
    _get_root_query_path = os.path.join(_queries_dir, "get_root.sparql")

    def __init__(
        self, rdf_description  # type: str
    ):
        """Create a viewer object based on the rdf description of the workflow."""
        self._dot_graph = CWLViewer._init_dot_graph()  # type: pydot.Graph
        self._rdf_graph = self._load_cwl_graph(
            rdf_description
        )  # type: rdflib.graph.Graph
        self._root_graph_uri = self._get_root_graph_uri()  # type: str
        self._set_inner_edges()
        self._set_input_edges()
        self._set_output_edges()

    def _load_cwl_graph(
        self, rdf_description  # type: str
    ) -> rdflib.graph.Graph:
        rdf_graph = rdflib.Graph()
        rdf_graph.parse(data=rdf_description, format="n3")
        return rdf_graph

    def _set_inner_edges(self) -> None:
        with open(self._get_inner_edges_query_path) as f:
            get_inner_edges_query = f.read()
        inner_edges = self._rdf_graph.query(
            get_inner_edges_query, initBindings={"root_graph": self._root_graph_uri}
        )
        for inner_edge_row in inner_edges:
            source_label = (
                inner_edge_row["source_label"]
                if inner_edge_row["source_label"] is not None
                else urlparse(inner_edge_row["source_step"]).fragment
            )
            n = pydot.Node(
                "",
                fillcolor="lightgoldenrodyellow",
                style="filled",
                label=source_label,
                shape="record",
            )
            n.set_name(str(inner_edge_row["source_step"]))
            self._dot_graph.add_node(n)
            target_label = (
                inner_edge_row["target_label"]
                if inner_edge_row["target_label"] is not None
                else urlparse(inner_edge_row["target_step"]).fragment
            )
            n = pydot.Node(
                "",
                fillcolor="lightgoldenrodyellow",
                style="filled",
                label=target_label,
                shape="record",
            )
            n.set_name(str(inner_edge_row["target_step"]))
            self._dot_graph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(
                    str(inner_edge_row["source_step"]),
                    str(inner_edge_row["target_step"]),
                )
            )

    def _set_input_edges(self) -> None:
        with open(self._get_input_edges_query_path) as f:
            get_input_edges_query = f.read()
        inputs_subgraph = pydot.Subgraph(graph_name="cluster_inputs")
        self._dot_graph.add_subgraph(inputs_subgraph)
        inputs_subgraph.set_rank("same")
        inputs_subgraph.create_attribute_methods(["style"])
        inputs_subgraph.set_style("dashed")
        inputs_subgraph.set_label("Workflow Inputs")

        input_edges = self._rdf_graph.query(
            get_input_edges_query, initBindings={"root_graph": self._root_graph_uri}
        )
        for input_row in input_edges:
            n = pydot.Node(
                "",
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(input_row["input"]).fragment,
                shape="record",
            )
            n.set_name(str(input_row["input"]))
            inputs_subgraph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(str(input_row["input"]), str(input_row["step"]))
            )

    def _set_output_edges(self) -> None:
        with open(self._get_output_edges_query_path) as f:
            get_output_edges = f.read()
        outputs_graph = pydot.Subgraph(graph_name="cluster_outputs")
        self._dot_graph.add_subgraph(outputs_graph)
        outputs_graph.set_rank("same")
        outputs_graph.create_attribute_methods(["style"])
        outputs_graph.set_style("dashed")
        outputs_graph.set_label("Workflow Outputs")
        outputs_graph.set_labelloc("b")
        output_edges = self._rdf_graph.query(
            get_output_edges, initBindings={"root_graph": self._root_graph_uri}
        )
        for output_edge_row in output_edges:
            n = pydot.Node(
                "",
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(output_edge_row["output"]).fragment,
                shape="record",
            )
            n.set_name(str(output_edge_row["output"]))
            outputs_graph.add_node(n)
            self._dot_graph.add_edge(
                pydot.Edge(output_edge_row["step"], output_edge_row["output"])
            )

    def _get_root_graph_uri(self) -> rdflib.URIRef:
        with open(self._get_root_query_path) as f:
            get_root_query = f.read()
        root = list(
            self._rdf_graph.query(
                get_root_query,
            )
        )
        if len(root) != 1:
            raise RuntimeError(
                "Cannot identify root workflow! Notice that only Workflows can be visualized"
            )

        workflow = root[0]["workflow"]  # type: rdflib.URIRef
        return workflow

    @classmethod
    def _init_dot_graph(cls) -> pydot.Graph:
        graph = pydot.Graph(graph_type="digraph", simplify=False)
        graph.set_bgcolor("#eeeeee")
        graph.set_clusterrank("local")
        graph.set_labelloc("bottom")
        graph.set_labelloc("bottom")
        graph.set_labeljust("right")

        return graph

    def get_dot_graph(self) -> pydot.Graph:
        """Get the dot graph object."""
        return self._dot_graph

    def dot(self) -> str:
        """Get the graph as graphviz."""
        return str(self._dot_graph.to_string())
