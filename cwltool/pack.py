import copy
import json

from schema_salad.ref_resolver import Loader

from .process import scandeps, shortname

from typing import Union, Any, cast, Callable, Dict, Tuple, Type, IO

def flatten_deps(d, files):  # type: (Any, Set[unicode]) -> None
    if isinstance(d, list):
        for s in d:
            flatten_deps(s, files)
    elif isinstance(d, dict):
        files.add(d["location"])
        if "secondaryFiles" in d:
            flatten_deps(d["secondaryFiles"], files)

def find_run(d, runs):  # type: (Any, Set[unicode]) -> None
    if isinstance(d, list):
        for s in d:
            find_run(s, runs)
    elif isinstance(d, dict):
        if "run" in d and isinstance(d["run"], (str, unicode)):
            runs.add(d["run"])
        for s in d.values():
            find_run(s, runs)

def replace_refs(d, rewrite, stem, newstem):
    # type: (Any, Dict[unicode, unicode], unicode, unicode) -> None
    if isinstance(d, list):
        for s,v in enumerate(d):
            if isinstance(v, (str, unicode)) and v.startswith(stem):
                d[s] = newstem + v[len(stem):]
            else:
                replace_refs(v, rewrite, stem, newstem)
    elif isinstance(d, dict):
        if "package" in d:
            raise Exception("where the fuck did this come from %s" % json.dumps(d, indent=4))
        if "run" in d and isinstance(d["run"], (str, unicode)):
            d["run"] = rewrite[d["run"]]
        for s,v in d.items():
            if isinstance(v, (str, unicode)) and v.startswith(stem):
                d[s] = newstem + v[len(stem):]
            replace_refs(v, rewrite, stem, newstem)

def pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[unicode, Any], List[Dict[unicode, Any]]], unicode, Dict[unicode, unicode]) -> Dict[unicode, Any]
    def loadref(b, u):
        # type: (unicode, unicode) -> Union[Dict, List, unicode]
        return document_loader.resolve_ref(u, base_url=b)[0]
    deps = scandeps(uri, processobj, set(("run",)), set(), loadref)

    fdeps = set((uri,))
    flatten_deps(deps, fdeps)

    runs = set()  # type: Set[unicode]
    for f in fdeps:
        find_run(document_loader.idx[f], runs)

    rewrite = {}
    if isinstance(processobj, list):
        for p in processobj:
            rewrite[p["id"]] = "#" + shortname(p["id"])
    else:
        rewrite[uri] = "#main"

    for r in runs:
        rewrite[r] = "#" + shortname(r)

    packed = {"$graph": [], "cwlVersion": metadata["cwlVersion"]
            }  # type: Dict[unicode, Any]
    for r,v in rewrite.items():
        dc = cast(Dict[unicode, Any], copy.deepcopy(document_loader.idx[r]))
        dc["id"] = v
        for n in ("name", "package", "cwlVersion"):
            if n in dc:
                del dc[n]
        replace_refs(dc, rewrite, r+"/" if "#" in r else r+"#", v+"/")
        packed["$graph"].append(dc)

    return packed
