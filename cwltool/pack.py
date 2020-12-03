"""Reformat a CWL document and all its references to be a single stream."""

import copy
import urllib
from typing import (
    Any,
    Callable,
    Dict,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    Union,
    cast,
)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.ref_resolver import Loader, ResolveType, SubLoader

from .context import LoadingContext
from .load_tool import fetch_document, resolve_and_validate_document
from .process import shortname, uniquename
from .update import ORDERED_VERSIONS, update
from .utils import CWLObjectType, CWLOutputType

LoadRefType = Callable[[Optional[str], str], ResolveType]


def find_run(
    d: Union[CWLObjectType, ResolveType],
    loadref: LoadRefType,
    runs: Set[str],
) -> None:
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


def find_ids(
    d: Union[CWLObjectType, CWLOutputType, MutableSequence[CWLObjectType], None],
    ids: Set[str],
) -> None:
    if isinstance(d, MutableSequence):
        for s in d:
            find_ids(cast(CWLObjectType, s), ids)
    elif isinstance(d, MutableMapping):
        for i in ("id", "name"):
            if i in d and isinstance(d[i], str):
                ids.add(cast(str, d[i]))
        for s2 in d.values():
            find_ids(cast(CWLOutputType, s2), ids)


def replace_refs(d: Any, rewrite: Dict[str, str], stem: str, newstem: str) -> None:
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
        for key, val in d.items():
            if isinstance(val, str):
                if val in rewrite:
                    d[key] = rewrite[val]
                elif val.startswith(stem):
                    id_ = val[len(stem) :]
                    # prevent appending newstems if tool is already packed
                    if id_.startswith(newstem.strip("#")):
                        d[key] = "#" + id_
                    else:
                        d[key] = newstem + id_
                    rewrite[val] = d[key]
            replace_refs(val, rewrite, stem, newstem)


def import_embed(
    d: Union[MutableSequence[CWLObjectType], CWLObjectType, CWLOutputType],
    seen: Set[str],
) -> None:
    if isinstance(d, MutableSequence):
        for v in d:
            import_embed(cast(CWLOutputType, v), seen)
    elif isinstance(d, MutableMapping):
        for n in ("id", "name"):
            if n in d:
                if isinstance(d[n], str):
                    ident = cast(str, d[n])
                    if ident in seen:
                        this = ident
                        d.clear()
                        d["$import"] = this
                    else:
                        this = ident
                        seen.add(this)
                        break

        for k in sorted(d.keys()):
            import_embed(cast(CWLOutputType, d[k]), seen)


def pack(
    loadingContext: LoadingContext,
    uri: str,
    rewrite_out: Optional[Dict[str, str]] = None,
    loader: Optional[Loader] = None,
) -> CWLObjectType:

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
    loadingContext = loadingContext.copy()
    document_loader = SubLoader(loader or loadingContext.loader or Loader({}))
    loadingContext.do_update = False
    loadingContext.loader = document_loader
    loadingContext.loader.idx = {}
    loadingContext.metadata = {}
    loadingContext, docobj, uri = fetch_document(uri, loadingContext)
    loadingContext, fileuri = resolve_and_validate_document(
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

    found_versions = {
        cast(str, loadingContext.metadata["cwlVersion"])
    }  # type: Set[str]

    def loadref(base: Optional[str], lr_uri: str) -> ResolveType:
        lr_loadingContext = loadingContext.copy()
        lr_loadingContext.metadata = {}
        lr_loadingContext, lr_workflowobj, lr_uri = fetch_document(
            lr_uri, lr_loadingContext
        )
        lr_loadingContext, lr_uri = resolve_and_validate_document(
            lr_loadingContext, lr_workflowobj, lr_uri
        )
        found_versions.add(cast(str, lr_loadingContext.metadata["cwlVersion"]))
        if lr_loadingContext.loader is None:
            raise Exception("loader should not be None")
        return lr_loadingContext.loader.resolve_ref(lr_uri, base_url=base)[0]

    ids = set()  # type: Set[str]
    find_ids(processobj, ids)

    runs = {uri}
    find_run(processobj, loadref, runs)

    # Figure out the highest version, everything needs to be updated
    # to it.
    m = 0
    for fv in found_versions:
        m = max(m, ORDERED_VERSIONS.index(fv))
    update_to_version = ORDERED_VERSIONS[m]

    for f in runs:
        find_ids(document_loader.resolve_ref(f)[0], ids)

    names = set()  # type: Set[str]
    if rewrite_out is None:
        rewrite = {}  # type: Dict[str, str]
    else:
        rewrite = rewrite_out

    mainpath, _ = urllib.parse.urldefrag(uri)

    def rewrite_id(r: str, mainuri: str) -> None:
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
        (("$graph", CommentedSeq()), ("cwlVersion", update_to_version))
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

        dcr = update(
            dcr,
            document_loader,
            r,
            loadingContext.enable_dev,
            metadata,
            update_to_version,
        )

        if "http://commonwl.org/cwltool#original_cwlVersion" in metadata:
            del metadata["http://commonwl.org/cwltool#original_cwlVersion"]
        if "http://commonwl.org/cwltool#original_cwlVersion" in dcr:
            del dcr["http://commonwl.org/cwltool#original_cwlVersion"]

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
