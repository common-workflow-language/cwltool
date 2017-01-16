import copy
import urlparse

from schema_salad.ref_resolver import Loader

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

def find_ids(d, ids):  # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            find_ids(s, ids)
    elif isinstance(d, dict):
        for i in ("id", "name"):
            if i in d and  isinstance(d[i], (str, unicode)):
                ids.add(d[i])
        for s in d.values():
            find_ids(s, ids)

def replace_refs(d, rewrite, stem, newstem):
    # type: (Any, Dict[Text, Text], Text, Text) -> None
    if isinstance(d, list):
        for s,v in enumerate(d):
            if isinstance(v, (str, unicode)):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    d[s] = newstem + v[len(stem):]
            else:
                replace_refs(v, rewrite, stem, newstem)
    elif isinstance(d, dict):
        for s,v in d.items():
            if isinstance(v, (str, unicode)):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    d[s] = newstem + v[len(stem):]
            replace_refs(v, rewrite, stem, newstem)

def pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Dict[Text, Text]) -> Dict[Text, Any]
    def loadref(b, u):
        # type: (Text, Text) -> Union[Dict, List, Text]
        return document_loader.resolve_ref(u, base_url=b)[0]
    deps = scandeps(uri, processobj, set(("run",)), set(), loadref)

    fdeps = set((uri,))
    flatten_deps(deps, fdeps)

    ids = set()  # type: Set[Text]
    for f in fdeps:
        find_ids(document_loader.idx[f], ids)

    names = set()  # type: Set[Text]
    rewrite = {}
    if isinstance(processobj, list):
        for p in processobj:
            rewrite[p["id"]] = "#" + uniquename(shortname(p["id"]), names)
    else:
        rewrite[uri] = "#main"

    sortedids = sorted(ids)

    for r in sortedids:
        path, frag = urlparse.urldefrag(r)
        if path not in rewrite:
            rewrite[path] = "#" + uniquename(shortname(path), names)
        if r != path:
            rewrite[r] = "%s/%s" % (rewrite[path], frag)

    packed = {"$graph": [], "cwlVersion": metadata["cwlVersion"]
            }  # type: Dict[Text, Any]

    for r in sortedids:
        dcr = document_loader.idx[r]
        if "$namespaces" in dcr:
            if "$namespaces" not in packed:
                packed["$namespaces"] = {}
            packed["$namespaces"].update(dcr["$namespaces"])
        if not isinstance(dcr, dict) or dcr.get("class") not in ("Workflow", "CommandLineTool", "ExpressionTool"):
            continue
        dc = cast(Dict[Text, Any], copy.deepcopy(dcr))
        v = rewrite[r]
        dc["id"] = v
        for n in ("name", "cwlVersion"):
            if n in dc:
                del dc[n]
        packed["$graph"].append(dc)

    for r in rewrite:
        v = rewrite[r]
        replace_refs(packed, rewrite, r+"/" if "#" in r else r+"#", v+"/")

    return packed
