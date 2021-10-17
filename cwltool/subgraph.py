import urllib
from collections import namedtuple
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    Tuple,
    cast,
)

from ruamel.yaml.comments import CommentedMap

from .utils import CWLObjectType, aslist
from .workflow import Workflow, WorkflowStep

Node = namedtuple("Node", ("up", "down", "type"))
UP = "up"
DOWN = "down"
INPUT = "input"
OUTPUT = "output"
STEP = "step"


def subgraph_visit(
    current: str,
    nodes: MutableMapping[str, Node],
    visited: Set[str],
    direction: str,
) -> None:

    if current in visited:
        return
    visited.add(current)

    if direction == DOWN:
        d = nodes[current].down
    if direction == UP:
        d = nodes[current].up
    for c in d:
        subgraph_visit(c, nodes, visited, direction)


def declare_node(nodes: Dict[str, Node], nodeid: str, tp: Optional[str]) -> Node:
    if nodeid in nodes:
        n = nodes[nodeid]
        if n.type is None:
            nodes[nodeid] = Node(n.up, n.down, tp)
    else:
        nodes[nodeid] = Node([], [], tp)
    return nodes[nodeid]


def find_step(steps: List[WorkflowStep], stepid: str) -> Optional[CWLObjectType]:
    for st in steps:
        if st.tool["id"] == stepid:
            return st.tool
    return None


def get_subgraph(roots: MutableSequence[str], tool: Workflow) -> CommentedMap:
    if tool.tool["class"] != "Workflow":
        raise Exception("Can only extract subgraph from workflow")

    nodes: Dict[str, Node] = {}

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
            if isinstance(out, Mapping) and "id" in out:
                out = out["id"]
            # output is downstream from step
            step.down.append(out)
            # step is upstream from output
            declare_node(nodes, out, None)
            nodes[out].up.append(st["id"])

    # Find all the downstream nodes from the starting points
    visited_down: Set[str] = set()
    for r in roots:
        if nodes[r].type == OUTPUT:
            subgraph_visit(r, nodes, visited_down, UP)
        else:
            subgraph_visit(r, nodes, visited_down, DOWN)

    # Now make sure all the nodes are connected to upstream inputs
    visited: Set[str] = set()
    rewire: Dict[str, Tuple[str, CWLObjectType]] = {}
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
                    rn = str(df[0] + "#" + df[1].replace("/", "_"))
                    if nodes[v].type == STEP:
                        wfstep = find_step(tool.steps, v)
                        if wfstep is not None:
                            for inp in cast(
                                MutableSequence[CWLObjectType], wfstep["inputs"]
                            ):
                                if "source" in inp and u in cast(
                                    CWLObjectType, inp["source"]
                                ):
                                    rewire[u] = (rn, cast(CWLObjectType, inp["type"]))
                                    break
                        else:
                            raise Exception("Could not find step %s" % v)

    extracted = CommentedMap()
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
                                inport["source"] = [
                                    rewire[s][0]
                                    for s in inport["source"]
                                    if s in rewire
                                ]
                            elif inport["source"] in rewire:
                                inport["source"] = rewire[inport["source"]][0]
                    extracted[f].append(i)
        else:
            extracted[f] = tool.tool[f]

    for rv in rewire.values():
        extracted["inputs"].append({"id": rv[0], "type": rv[1]})

    return extracted


def get_step(tool: Workflow, step_id: str) -> CommentedMap:

    extracted = CommentedMap()

    step = find_step(tool.steps, step_id)
    if step is None:
        raise Exception(f"Step {step_id} was not found")

    extracted["steps"] = [step]
    extracted["inputs"] = []
    extracted["outputs"] = []

    for inport in cast(List[CWLObjectType], step["in"]):
        name = cast(str, inport["id"]).split("#")[-1].split("/")[-1]
        extracted["inputs"].append({"id": name, "type": "Any"})
        inport["source"] = name
        if "linkMerge" in inport:
            del inport["linkMerge"]

    for outport in cast(List[str], step["out"]):
        name = outport.split("#")[-1].split("/")[-1]
        extracted["outputs"].append(
            {"id": name, "type": "Any", "outputSource": f"{step_id}/{name}"}
        )

    for f in tool.tool:
        if f not in ("steps", "inputs", "outputs"):
            extracted[f] = tool.tool[f]

    return extracted


def get_process(tool: Workflow, step_id: str, index: Mapping[str, Any]) -> Any:
    """Return just a single Process from a Workflow step."""
    step = find_step(tool.steps, step_id)
    if step is None:
        raise Exception(f"Step {step_id} was not found")

    run = step["run"]

    if isinstance(run, str):
        return index[run]
    else:
        return run
