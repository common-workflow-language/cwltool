import copy
from .utils import aslist, json_dumps
from collections import namedtuple
from typing import (Dict, MutableMapping, MutableSequence, Set, Any, Text, Optional, Tuple)
from .process import shortname
from six import itervalues
from six.moves import urllib
from .workflow import Workflow

Node = namedtuple('Node', ('up', 'down', 'type'))
UP = "up"
DOWN = "down"
INPUT = "input"
OUTPUT = "output"
STEP = "step"

def subgraph_visit(current,   # type: Text
                   nodes,     # type: MutableMapping[Text, Node]
                   visited,   # type: Set[Text]
                   direction  # type: Text
): # type: (...) -> None

    if current in visited:
        return
    visited.add(current)

    if direction == DOWN:
        d = nodes[current].down
    if direction == UP:
        d = nodes[current].up
    for c in d:
        subgraph_visit(c, nodes, visited, direction)

def declare_node(nodes, nodeid, tp):
    # type: (Dict[Text, Node], Text, Optional[Text]) -> Node
    if nodeid in nodes:
        n = nodes[nodeid]
        if n.type is None:
            nodes[nodeid] = Node(n.up, n.down, tp)
    else:
        nodes[nodeid] = Node([], [], tp)
    return nodes[nodeid]

def get_subgraph(roots,  # type: MutableSequence[Text]
                 tool    # type: Workflow
):
    if tool.tool["class"] != "Workflow":
        raise Exception("Can only extract subgraph from workflow")

    nodes = {}  # type: Dict[Text, Node]

    for inp in tool.tool["inputs"]:
        declare_node(nodes, inp["id"], INPUT)

    for out in tool.tool["outputs"]:
        declare_node(nodes, out["id"], OUTPUT)
        for i in aslist(out.get("outputSource", [])):
            # source is upstream from output (dependency)
            nodes[out["id"]].up.append(i)
            # output is downstream from source
            declare_node(nodes, i, None)
            nodes[i].down.append(out["id"])

    for st in tool.tool["steps"]:
        step = declare_node(nodes, st["id"], STEP)
        for i in st["in"]:
            if "source" not in i:
                continue
            for src in aslist(i["source"]):
                # source is upstream from step (dependency)
                step.up.append(src)
                # step is downstream from source
                declare_node(nodes, src, None)
                nodes[src].down.append(st["id"])
        for out in st["out"]:
            # output is downstream from step
            step.down.append(out)
            # step is upstream from output
            declare_node(nodes, out, None)
            nodes[out].up.append(st["id"])


    # Find all the downstream nodes from the starting points
    visited_down = set()  # type: Set[Text]
    for r in roots:
        if nodes[r].type == OUTPUT:
            subgraph_visit(r, nodes, visited_down, UP)
        else:
            subgraph_visit(r, nodes, visited_down, DOWN)

    def find_step(stepid):  # type: (Text) -> Optional[MutableMapping]
        for st in tool.steps:
            if st.tool["id"] == stepid:
                return st.tool
        return None

    # Now make sure all the nodes are connected to upstream inputs
    visited = set()  # type: Set[Text]
    rewire = {}  # type: Dict[Text, Tuple[Text, Text]]
    for v in visited_down:
        visited.add(v)
        if nodes[v].type in (STEP, OUTPUT):
            for u in nodes[v].up:
                if u in visited_down:
                    continue
                if nodes[u].type == INPUT:
                    visited.add(u)
                else:
                    # rewire
                    df = urllib.parse.urldefrag(u)
                    rn = df[0] + "#" + df[1].replace("/", "_")
                    if nodes[v].type == STEP:
                        wfstep = find_step(v)
                        if wfstep is not None:
                            for inp in wfstep["inputs"]:
                                if u in inp["source"]:
                                    rewire[u] = (rn, inp["type"])
                                    break
                        else:
                            raise Exception("Could not find step %s" % v)


    extracted = {}  # type: MutableMapping[Text, Any]
    for f in tool.tool:
        if f in ("steps", "inputs", "outputs"):
            extracted[f] = []
            for i in tool.tool[f]:
                if i["id"] in visited:
                    if f == "steps":
                        for inport in i["in"]:
                            if "source" not in inport:
                                continue
                            if isinstance(inport["source"], MutableSequence):
                                inport["source"] = [rewire[s][0] for s in inport["source"] if s in rewire]
                            elif inport["source"] in rewire:
                                inport["source"] = rewire[inport["source"]][0]
                    extracted[f].append(i)
        else:
            extracted[f] = tool.tool[f]

    for rv in itervalues(rewire):
        extracted["inputs"].append({
            "id": rv[0],
            "type": rv[1]
        })

    return extracted
