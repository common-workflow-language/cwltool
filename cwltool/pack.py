import copy
import json

from schema_salad.ref_resolver import Loader
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .process import scandeps, shortname, uniquename

from typing import Union, Any, cast, Callable, Dict, Tuple, Type, IO, Text

def flatten_deps(d, files):  # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            flatten_deps(s, files)
    elif isinstance(d, dict):
        if d["class"] == "File":
            files.add(d["location"])
        if "secondaryFiles" in d:
            flatten_deps(d["secondaryFiles"], files)
        if "listing" in d:
            flatten_deps(d["listing"], files)

def find_run(d, runs):  # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            find_run(s, runs)
    elif isinstance(d, dict):
        if "run" in d and isinstance(d["run"], (str, unicode)):
            runs.add(d["run"])
        for s in d.values():
            find_run(s, runs)

def replace_refs(d, rewrite, stem, newstem):
    # type: (Any, Dict[Text, Text], Text, Text) -> None
    if isinstance(d, list):
        for s,v in enumerate(d):
            if isinstance(v, (str, unicode)) and v.startswith(stem):
                d[s] = newstem + v[len(stem):]
            else:
                replace_refs(v, rewrite, stem, newstem)
    elif isinstance(d, dict):
        if "run" in d and isinstance(d["run"], (str, unicode)):
            d["run"] = rewrite[d["run"]]
        for s,v in d.items():
            if isinstance(v, (str, unicode)) and v.startswith(stem):
                d[s] = newstem + v[len(stem):]
            replace_refs(v, rewrite, stem, newstem)

def yamlcopy(d):
    if isinstance(d, CommentedMap):
        cm = CommentedMap()
        for k,v in d.iteritems():
            cm[k] = yamlcopy(v)
        cm.__dict__ = copy.deepcopy(d.__dict__)
        return cm
    elif isinstance(d, CommentedSeq):
        cs = CommentedSeq()
        for v in d:
            cs.append(yamlcopy(v))
        cs.__dict__ = copy.deepcopy(d.__dict__)
        return cs
    elif isinstance(d, dict):
        return {k: yamlcopy(v) for k,v in d.iteritems()}
    elif isinstance(d, list):
        return [yamlcopy(v) for v in d]
    else:
        return d

def pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Dict[Text, Text]) -> Dict[Text, Any]
    def loadref(b, u):
        # type: (Text, Text) -> Union[Dict, List, Text]
        return document_loader.resolve_ref(u, base_url=b)[0]
    deps = scandeps(uri, processobj, set(("run",)), set(), loadref)

    fdeps = set((uri,))
    flatten_deps(deps, fdeps)

    runs = set()  # type: Set[Text]
    for f in fdeps:
        find_run(document_loader.idx[f], runs)

    names = set()  # type: Set[Text]
    rewrite = {}
    if isinstance(processobj, list):
        for p in processobj:
            rewrite[p["id"]] = "#" + uniquename(shortname(p["id"]), names)
    else:
        rewrite[uri] = "#main"

    for r in sorted(runs):
        rewrite[r] = "#" + uniquename(shortname(r), names)

    packed = {"$graph": [], "cwlVersion": metadata["cwlVersion"]
            }  # type: Dict[Text, Any]

    for r in sorted(rewrite.keys()):
        v = rewrite[r]
        dc = cast(Dict[Text, Any], yamlcopy(document_loader.idx[r]))
        dc["id"] = v
        for n in ("name", "cwlVersion"):
            if n in dc:
                del dc[n]
        replace_refs(dc, rewrite, r+"/" if "#" in r else r+"#", v+"/")
        packed["$graph"].append(dc)

    return packed
