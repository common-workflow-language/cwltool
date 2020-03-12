"""Reformat a CWL document and all its references to be a single stream."""

import copy
import urllib
from typing import (
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    Union,
    cast,
)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.ref_resolver import Loader, SubLoader
from schema_salad.sourceline import cmap

from .process import shortname, uniquename
from .context import LoadingContext
from .load_tool import fetch_document, resolve_and_validate_document


def flatten_deps(d, files):  # type: (Any, Set[str]) -> None
    if isinstance(d, MutableSequence):
        for s in d:
            flatten_deps(s, files)
    elif isinstance(d, MutableMapping):
        if d["class"] == "File":
            files.add(d["location"])
        if "secondaryFiles" in d:
            flatten_deps(d["secondaryFiles"], files)
        if "listing" in d:
            flatten_deps(d["listing"], files)


LoadRefType = Callable[
    [Optional[str], str], Union[Dict[str, Any], List[Dict[str, Any]], str, None]
]


def find_run(
    d,  # type: Any
    loadref,  # type: LoadRefType
    runs,  # type: Set[str]
):  # type: (...) -> None
    if isinstance(d, MutableSequence):
        for s in d:
            find_run(s, loadref, runs)
    elif isinstance(d, MutableMapping):
        if "run" in d and isinstance(d["run"], str):
            if d["run"] not in runs:
                runs.add(d["run"])
                find_run(loadref(None, d["run"]), loadref, runs)
        for s in d.values():
            find_run(s, loadref, runs)


def find_ids(d, ids):  # type: (Any, Set[str]) -> None
    if isinstance(d, MutableSequence):
        for s in d:
            find_ids(s, ids)
    elif isinstance(d, MutableMapping):
        for i in ("id", "name"):
            if i in d and isinstance(d[i], str):
                ids.add(d[i])
        for s in d.values():
            find_ids(s, ids)


def replace_refs(d, rewrite, stem, newstem):
    # type: (Any, Dict[str, str], str, str) -> None
    if isinstance(d, MutableSequence):
        for s, v in enumerate(d):
            if isinstance(v, str):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    d[s] = newstem + v[len(stem) :]
                    rewrite[v] = d[s]
            else:
                replace_refs(v, rewrite, stem, newstem)
    elif isinstance(d, MutableMapping):
        for s, v in d.items():
            if isinstance(v, str):
                if v in rewrite:
                    d[s] = rewrite[v]
                elif v.startswith(stem):
                    id_ = v[len(stem) :]
                    # prevent appending newstems if tool is already packed
                    if id_.startswith(newstem.strip("#")):
                        d[s] = "#" + id_
                    else:
                        d[s] = newstem + id_
                    rewrite[v] = d[s]
            replace_refs(v, rewrite, stem, newstem)


def import_embed(d, seen):
    # type: (Any, Set[str]) -> None
    if isinstance(d, MutableSequence):
        for v in d:
            import_embed(v, seen)
    elif isinstance(d, MutableMapping):
        for n in ("id", "name"):
            if n in d:
                if isinstance(d[n], str):
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


def pack(
    document_loader: Loader,
    startingobj,  # type: Union[Dict[str, Any], List[Dict[str, Any]]]
    uri,  # type: str
    metadata,  # type: Dict[str, str]
    rewrite_out=None,  # type: Optional[Dict[str, str]]
):  # type: (...) -> Dict[str, Any]

    # The workflow document we have in memory right now may have been
    # updated to the internal CWL version.  We need to reload the
    # document to go back to its original version.
    #
    # What's going on here is that the updater replaces the
    # documents/fragments in the index with updated ones, the
    # index is also used as a cache, so we need to go through the
    # loading process with an empty index and updating turned off
    # so we have the original un-updated documents.
    #
    document_loader = SubLoader(document_loader)
    loadingContext = LoadingContext()
    loadingContext.do_update = False
    loadingContext.loader = document_loader
    loadingContext.loader.idx = {}
    loadingContext.metadata = {}
    loadingContext, docobj, uri = fetch_document(uri, loadingContext)
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, docobj, uri, preprocess_only=True
    )
    if loadingContext.loader is None:
        raise Exception("loadingContext.loader cannot be none")
    processobj, metadata = loadingContext.loader.resolve_ref(uri)
    document_loader = loadingContext.loader

    if isinstance(processobj, MutableMapping):
        document_loader.idx[processobj["id"]] = CommentedMap(processobj.items())
    elif isinstance(processobj, MutableSequence):
        _, frag = urllib.parse.urldefrag(uri)
        for po in processobj:
            if not frag:
                if po["id"].endswith("#main"):
                    uri = po["id"]
            document_loader.idx[po["id"]] = CommentedMap(po.items())
        document_loader.idx[metadata["id"]] = CommentedMap(metadata.items())

    def loadref(base, uri):
        # type: (Optional[str], str) -> Union[Dict[str, Any], List[Dict[str, Any]], str, None]
        return document_loader.resolve_ref(uri, base_url=base)[0]

    ids = set()  # type: Set[str]
    find_ids(processobj, ids)

    runs = {uri}
    find_run(processobj, loadref, runs)

    for f in runs:
        find_ids(document_loader.resolve_ref(f)[0], ids)

    names = set()  # type: Set[str]
    if rewrite_out is None:
        rewrite = {}  # type: Dict[str, str]
    else:
        rewrite = rewrite_out

    mainpath, _ = urllib.parse.urldefrag(uri)

    def rewrite_id(r, mainuri):
        # type: (str, str) -> None
        if r == mainuri:
            rewrite[r] = "#main"
        elif r.startswith(mainuri) and r[len(mainuri)] in ("#", "/"):
            if r[len(mainuri) :].startswith("#main/"):
                rewrite[r] = "#" + uniquename(r[len(mainuri) + 1 :], names)
            else:
                rewrite[r] = "#" + uniquename("main/" + r[len(mainuri) + 1 :], names)
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

    packed = CommentedMap(
        (("$graph", CommentedSeq()), ("cwlVersion", metadata["cwlVersion"]))
    )
    namespaces = metadata.get("$namespaces", None)

    schemas = set()  # type: Set[str]
    if "$schemas" in metadata:
        for each_schema in metadata["$schemas"]:
            schemas.add(each_schema)
    for r in sorted(runs):
        dcr, metadata = document_loader.resolve_ref(r)
        if isinstance(dcr, CommentedSeq):
            dcr = dcr[0]
            dcr = cast(CommentedMap, dcr)
        if not isinstance(dcr, MutableMapping):
            continue
        metadata = cast(Dict[str, Any], metadata)
        if "$schemas" in metadata:
            for s in metadata["$schemas"]:
                schemas.add(s)
        if dcr.get("class") not in ("Workflow", "CommandLineTool", "ExpressionTool"):
            continue
        dc = cast(Dict[str, Any], copy.deepcopy(dcr))
        v = rewrite[r]
        dc["id"] = v
        for n in ("name", "cwlVersion", "$namespaces", "$schemas"):
            if n in dc:
                del dc[n]
        packed["$graph"].append(dc)

    if schemas:
        packed["$schemas"] = list(schemas)

    for r in list(rewrite.keys()):
        v = rewrite[r]
        replace_refs(packed, rewrite, r + "/" if "#" in r else r + "#", v + "/")

    import_embed(packed, set())

    if len(packed["$graph"]) == 1:
        # duplicate 'cwlVersion' and $schemas inside $graph when there is only
        # a single item because we will print the contents inside '$graph'
        # rather than whole dict
        packed["$graph"][0]["cwlVersion"] = packed["cwlVersion"]
        if schemas:
            packed["$graph"][0]["$schemas"] = list(schemas)
    # always include $namespaces in the #main
    if namespaces:
        packed["$graph"][0]["$namespaces"] = namespaces

    return packed
