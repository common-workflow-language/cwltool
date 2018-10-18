import copy
from .utils import aslist, json_dumps
from collections import namedtuple

Node = namedtuple('Node', ('up', 'down'))
UP = "up"
DOWN = "down"

def subgraph_visit(current, nodes, visited, direction):
    if current in visited:
        return
    visited.add(current)

    if direction == DOWN:
        d = nodes[current].down
    if direction == UP:
        d = nodes[current].up
    for c in d:
        subgraph_visit(c, nodes, visited, direction)


def get_subgraph(roots, tool):
    if tool.tool["class"] != "Workflow":
        raise Exception("Can only extract subgraph from workflow")

    nodes = {}

    for inp in tool.tool["inputs"]:
        nodes.setdefault(inp["id"], Node([], []))

    for st in tool.tool["steps"]:
        step = nodes.setdefault(st["id"], Node([], []))
        for i in st["in"]:
            if "source" not in i:
                continue
            for src in aslist(i["source"]):
                # source is upstream from step (dependency)
                step.up.append(src)
                # step is downstream from source
                nodes.setdefault(src, Node([], []))
                nodes[src].down.append(st["id"])
        for out in st["out"]:
            # output is downstream from step
            step.down.append(out)
            # step is upstream from output
            nodes.setdefault(out, Node([], []))
            nodes[out].up.append(st["id"])

    for out in tool.tool["outputs"]:
        nodes.setdefault(out["id"], Node([], []))
        for i in aslist(out.get("outputSource", [])):
            # source is upstream from output (dependency)
            nodes[out["id"]].up.append(i)
            # output is downstream from step
            nodes.setdefault(i, Node([], []))
            nodes[i].down.append(out["id"])

    import pprint
    pprint.pprint(nodes)

    # Find all the downstream nodes from the starting points
    visited_down = set()
    for r in roots:
        subgraph_visit(r, nodes, visited_down, DOWN)

    # Now get all the dependencies of the downstream nodes
    visited = set()
    for v in visited_down:
        subgraph_visit(v, nodes, visited, UP)

    extracted = {}
    for f in tool.tool:
        if f in ("steps", "inputs", "outputs"):
            extracted[f] = []
            for i in tool.tool[f]:
                if i["id"] in visited:
                    extracted[f].append(i)
        else:
            extracted[f] = tool.tool[f]

    return extracted
