from __future__ import absolute_import
import copy
import re
from typing import Any, Callable, Dict, List, Set, Text, Union, cast

from schema_salad.ref_resolver import Loader, SubLoader
from six.moves import urllib
from ruamel.yaml.comments import CommentedSeq, CommentedMap

from .process import shortname, uniquename
import six


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


def find_run(d, loadref, runs):  # type: (Any, Callable[[Text, Text], Union[Dict, List, Text]], Set[Text]) -> None
    if isinstance(d, list):
        for s in d:
            find_run(s, loadref, runs)
    elif isinstance(d, dict):
        if "run" in d and isinstance(d["run"], six.string_types):
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
            if i in d and isinstance(d[i], six.string_types):
                ids.add(d[i])
        for s in d.values():
            find_ids(s, ids)


def replace_refs(d, rewrite, stem, newstem):
    # type: (Any, Dict[Text, Text], Text, Text) -> None
    if isinstance(d, list):
        for s, v in enumerate(d):
            if isinstance(v, six.string_types):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    d[s] = newstem + v[len(stem):]
            else:
                replace_refs(v, rewrite, stem, newstem)
    elif isinstance(d, dict):
        for s, v in d.items():
            if isinstance(v, six.string_types):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    id_ = v[len(stem):]
                    # prevent appending newstems if tool is already packed
                    if id_.startswith(newstem.strip("#")):
                        d[s] = "#" + id_
                    else:
                        d[s] = newstem + id_
            replace_refs(v, rewrite, stem, newstem)

def import_embed(d, seen):
    # type: (Any, Set[Text]) -> None
    if isinstance(d, list):
        for v in d:
            import_embed(v, seen)
    elif isinstance(d, dict):
        for n in ("id", "name"):
            if n in d:
                if d[n] in seen:
                    this = d[n]
                    d.clear()
                    d["$import"] = this
                else:
                    this = d[n]
                    seen.add(this)
                    break

        for k in sorted(d.keys()):
            import_embed(d[k], seen)


def pack(document_loader, processobj, uri, metadata, rewrite_out=None):
    # type: (Loader, Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Dict[Text, Text], Dict[Text, Text]) -> Dict[Text, Any]

    document_loader = SubLoader(document_loader)
    document_loader.idx = {}
    if isinstance(processobj, dict):
        document_loader.idx[processobj["id"]] = CommentedMap(six.iteritems(processobj))
    elif isinstance(processobj, list):
        path, frag = urllib.parse.urldefrag(uri)
        for po in processobj:
            if not frag:
                if po["id"].endswith("#main"):
                    uri = po["id"]
            document_loader.idx[po["id"]] = CommentedMap(six.iteritems(po))

    def loadref(b, u):
        # type: (Text, Text) -> Union[Dict, List, Text]
        return document_loader.resolve_ref(u, base_url=b)[0]

    ids = set()  # type: Set[Text]
    find_ids(processobj, ids)

    runs = {uri}
    find_run(processobj, loadref, runs)

    for f in runs:
        find_ids(document_loader.resolve_ref(f)[0], ids)

    names = set()  # type: Set[Text]
    if rewrite_out is None:
        rewrite = {}  # type: Dict[Text, Text]
    else:
        rewrite = rewrite_out

    mainpath, _ = urllib.parse.urldefrag(uri)

    def rewrite_id(r, mainuri):
        # type: (Text, Text) -> None
        if r == mainuri:
            rewrite[r] = "#main"
        elif r.startswith(mainuri) and r[len(mainuri)] in ("#", "/"):
            if r[len(mainuri):].startswith("#main/"):
                rewrite[r] = "#" + uniquename(r[len(mainuri)+1:], names)
            else:
                rewrite[r] = "#" + uniquename("main/"+r[len(mainuri)+1:], names)
        else:
            path, frag = urllib.parse.urldefrag(r)
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
    namespaces = metadata.get('$namespaces', None)

    schemas = set()  # type: Set[Text]
    for r in sorted(runs):
        dcr, metadata = document_loader.resolve_ref(r)
        if isinstance(dcr, CommentedSeq):
            dcr = dcr[0]
            dcr = cast(CommentedMap, dcr)
        if not isinstance(dcr, dict):
            continue
        for doc in (dcr, metadata):
            if "$schemas" in doc:
                for s in doc["$schemas"]:
                    schemas.add(s)
        if dcr.get("class") not in ("Workflow", "CommandLineTool", "ExpressionTool"):
            continue
        dc = cast(Dict[Text, Any], copy.deepcopy(dcr))
        v = rewrite[r]
        dc["id"] = v
        for n in ("name", "cwlVersion", "$namespaces", "$schemas"):
            if n in dc:
                del dc[n]
        packed["$graph"].append(dc)

    if schemas:
        packed["$schemas"] = list(schemas)

    for r in rewrite:
        v = rewrite[r]
        replace_refs(packed, rewrite, r + "/" if "#" in r else r + "#", v + "/")

    import_embed(packed, set())

    if len(packed["$graph"]) == 1:
        # duplicate 'cwlVersion' inside $graph when there is a single item
        # because we're printing contents inside '$graph' rather than whole dict
        packed["$graph"][0]["cwlVersion"] = packed["cwlVersion"]
    if namespaces:
        packed["$graph"][0]["$namespaces"] = dict(cast(Dict, namespaces))

    return packed
