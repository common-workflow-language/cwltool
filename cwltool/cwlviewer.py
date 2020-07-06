import rdflib
import pygraphviz as pgv
from urllib.parse import urlparse
import os


class CWLViewer:
    """
    Visualize a CWL workflow. The viewer tagrets to produce similar images with the
    https://github.com/common-workflow-language/cwlviewer.
    """

    _queries_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'rdfqueries')
    _get_inner_edges_query_path = os.path.join(_queries_dir, 'get_inner_edges.sparql')
    _get_input_edges_query_path = os.path.join(_queries_dir, 'get_input_edges.sparql')
    _get_output_edges_query_path = os.path.join(_queries_dir, 'get_output_edges.sparql')
    _get_root_query_path = os.path.join(_queries_dir, 'get_root.sparql')

    def __init__(self, rdf_description: str):
        self._dot_graph: pgv.agraph.AGraph = CWLViewer._init_dot_graph()
        self._rdf_graph: rdflib.graph.Graph = self._load_cwl_graph(rdf_description)
        self._root_graph_uri: str = self.get_root_graph_uri()
        self._set_inner_edges()
        self._set_input_edges()
        self._set_output_edges()

    # def _cwl2rdf(self) -> str:
    #     console_handler = logging.StreamHandler()
    #     console_handler.setLevel(logging.INFO)
    #     stdout = StringIO()
    #     cwltool_main(['--print-rdf', str(self._filename)], stdout=stdout, logger_handler=console_handler)
    #     return stdout.getvalue()

    def _load_cwl_graph(self, rdf_description: str) -> rdflib.graph.Graph:
        rdf_graph = rdflib.Graph()
        rdf_graph.parse(data=rdf_description, format='n3')
        return rdf_graph

    def _set_inner_edges(self):
        with open(self._get_inner_edges_query_path) as f:
            get_inner_edges_query = f.read()
        inner_edges = self._rdf_graph.query(get_inner_edges_query, initBindings={'root_graph': self._root_graph_uri})
        for inner_edge_row in inner_edges:
            source_label = inner_edge_row['source_label'] \
                if inner_edge_row['source_label'] is not None \
                else urlparse(inner_edge_row['source_step']).fragment
            self._dot_graph.add_node(
                inner_edge_row['source_step'],
                fillcolor='lightgoldenrodyellow', style="filled",
                label=source_label
            )
            target_label = inner_edge_row['target_label'] \
                if inner_edge_row['target_label'] is not None \
                else urlparse(inner_edge_row['target_step']).fragment
            self._dot_graph.add_node(
                inner_edge_row['target_step'],
                fillcolor='lightgoldenrodyellow', style="filled",
                label=target_label,
            )
            self._dot_graph.add_edge(inner_edge_row['source_step'], inner_edge_row['target_step'])

    def _set_input_edges(self):
        with open(self._get_input_edges_query_path) as f:
            get_input_edges_query = f.read()
        inputs_subgraph = self._dot_graph.add_subgraph(name="cluster_inputs")
        inputs_subgraph.graph_attr['rank'] = "same"
        inputs_subgraph.graph_attr['style'] = "dashed"
        inputs_subgraph.graph_attr['label'] = "Workflow Inputs"
        input_edges = self._rdf_graph.query(get_input_edges_query, initBindings={'root_graph': self._root_graph_uri})
        for input_row in input_edges:
            inputs_subgraph.add_node(
                input_row['input'],
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(input_row['input']).fragment,
            )
            self._dot_graph.add_edge(input_row['input'], input_row['step'])

    def _set_output_edges(self):
        with open(self._get_output_edges_query_path) as f:
            get_output_edges = f.read()

        outputs_graph = self._dot_graph.add_subgraph(name="cluster_outputs")
        outputs_graph.graph_attr['rank'] = "same"
        outputs_graph.graph_attr['style'] = "dashed"
        outputs_graph.graph_attr['label'] = "Workflow Outputs"
        outputs_graph.graph_attr['labelloc'] = "b"
        output_edges = self._rdf_graph.query(get_output_edges, initBindings={'root_graph': self._root_graph_uri})
        for output_edge_row in output_edges:
            outputs_graph.add_node(
                output_edge_row['output'],
                fillcolor="#94DDF4",
                style="filled",
                label=urlparse(output_edge_row['output']).fragment,
            )
            self._dot_graph.add_edge(output_edge_row['step'], output_edge_row['output'])

    def get_root_graph_uri(self):
        with open(self._get_root_query_path) as f:
            get_root_query = f.read()
        root = list(self._rdf_graph.query(get_root_query, ))[0]
        return root['workflow']

    @classmethod
    def _init_dot_graph(cls) -> pgv.agraph.AGraph:
        graph = pgv.AGraph(directed=True, strict=False)
        graph.graph_attr['bgcolor'] = "#eeeeee"
        graph.graph_attr['labeljust'] = "left"
        graph.graph_attr['clusterrank'] = "local"
        graph.node_attr['shape'] = "record"
        graph.graph_attr['labelloc'] = "bottom"
        graph.graph_attr['labeljust'] = "right"

        return graph

    def get_dot_graph(self) -> pgv.AGraph:
        return self._dot_graph

    def dot(self):
        return self._dot_graph.to_string()
