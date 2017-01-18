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

def find_run(d, loadref, runs):  # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            find_run(s, loadref, runs)
    elif isinstance(d, dict):
        if "run" in d and isinstance(d["run"], (str, unicode)):
            if d["run"] not in runs:
                runs.add(d["run"])
                find_run(loadref(None, d["run"]), loadref, runs)
        for s in d.values():
            find_run(s, loadref, runs)

def find_ids(d, ids):  # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            find_ids(s, ids)
    elif isinstance(d, dict):
        for i in ("id", "name"):
            if i in d and isinstance(d[i], (str, unicode)):
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

    runs = set((uri,))
    find_run(processobj, loadref, runs)

    #deps = scandeps(uri, processobj, set(("run",)), set(), loadref)
    #fdeps = set((uri,))
    #flatten_deps(deps, fdeps)

    ids = set()  # type: Set[Text]
    for f in runs:
        find_ids(document_loader.resolve_ref(f)[0], ids)

    names = set()  # type: Set[Text]
    rewrite = {}

    mainpath, _ = urlparse.urldefrag(uri)

    def rewrite_id(r, mainuri):
        if r == mainuri:
            rewrite[r] = "#main"
        elif r.startswith(mainuri) and r[len(mainuri)] in ("#", "/"):
            pass
        else:
            path, frag = urlparse.urldefrag(r)
            if path == mainpath:
                rewrite[r] = "#" + uniquename(frag, names)
            else:
                if path not in rewrite:
                    rewrite[path] = "#" + uniquename(shortname(path), names)

    sortedids = sorted(ids)

    for r in sortedids:
        rewrite_id(r, uri)

    packed = {"$graph": [], "cwlVersion": metadata["cwlVersion"]
            }  # type: Dict[Text, Any]

    for r in sorted(runs):
        dcr = document_loader.resolve_ref(r)[0]
        if "$namespaces" in dcr:
            if "$namespaces" not in packed:
                packed["$namespaces"] = {}
            packed["$namespaces"].update(dcr["$namespaces"])
        if not isinstance(dcr, dict) or dcr.get("class") not in ("Workflow", "CommandLineTool", "ExpressionTool"):
            continue
        dc = cast(Dict[Text, Any], copy.deepcopy(dcr))
        v = rewrite[r]
        dc["id"] = v
        for n in ("name", "cwlVersion", "$namespaces"):
            if n in dc:
                del dc[n]
        packed["$graph"].append(dc)

    for r in rewrite:
        v = rewrite[r]
        replace_refs(packed, rewrite, r+"/" if "#" in r else r+"#", v+"/")

    return packed
