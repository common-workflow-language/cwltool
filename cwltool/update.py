import sys
import urlparse
import json
import re
import traceback
import copy

from schema_salad.ref_resolver import Loader
import schema_salad.validate
from typing import Any, Callable, Dict, List, Text, Tuple, Union  # pylint: disable=unused-import

from ruamel.yaml.comments import CommentedSeq, CommentedMap

from .utils import aslist

def findId(doc, frg):  # type: (Any, Any) -> Dict
    if isinstance(doc, dict):
        if "id" in doc and doc["id"] == frg:
            return doc
        else:
            for d in doc:
                f = findId(doc[d], frg)
                if f:
                    return f
    if isinstance(doc, list):
        for d in doc:
            f = findId(d, frg)
            if f:
                return f
    return None

def fixType(doc):  # type: (Any) -> Any
    if isinstance(doc, list):
        for i, f in enumerate(doc):
            doc[i] = fixType(f)
        return doc

    if isinstance(doc, (str, Text)):
        if doc not in (
                "null", "boolean", "int", "long", "float", "double", "string",
                "File", "record", "enum", "array", "Any") and "#" not in doc:
            return "#" + doc
    return doc

def _draft2toDraft3dev1(doc, loader, baseuri, update_steps=True):
    # type: (Any, Loader, Text, bool) -> Any
    try:
        if isinstance(doc, dict):
            if "import" in doc:
                imp = urlparse.urljoin(baseuri, doc["import"])
                impLoaded = loader.fetch(imp)
                r = None  # type: Dict[Text, Any]
                if isinstance(impLoaded, list):
                    r = {"@graph": impLoaded}
                elif isinstance(impLoaded, dict):
                    r = impLoaded
                else:
                    raise Exception("Unexpected code path.")
                r["id"] = imp
                _, frag = urlparse.urldefrag(imp)
                if frag:
                    frag = "#" + frag
                    r = findId(r, frag)
                return _draft2toDraft3dev1(r, loader, imp)

            if "include" in doc:
                return loader.fetch_text(urlparse.urljoin(baseuri, doc["include"]))

            for typename in ("type", "items"):
                if typename in doc:
                    doc[typename] = fixType(doc[typename])

            if "steps" in doc and update_steps:
                if not isinstance(doc["steps"], list):
                    raise Exception("Value of 'steps' must be a list")
                for i, s in enumerate(doc["steps"]):
                    if "id" not in s:
                        s["id"] = "step%i" % i
                    for inp in s.get("inputs", []):
                        if isinstance(inp.get("source"), list):
                            if "requirements" not in doc:
                                doc["requirements"] = []
                            doc["requirements"].append({"class": "MultipleInputFeatureRequirement"})


            for a in doc:
                doc[a] = _draft2toDraft3dev1(doc[a], loader, baseuri)

        if isinstance(doc, list):
            for i, a in enumerate(doc):
                doc[i] = _draft2toDraft3dev1(a, loader, baseuri)

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))

def draft2toDraft3dev1(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (_draft2toDraft3dev1(doc, loader, baseuri), "draft-3.dev1")


digits = re.compile("\d+")

def updateScript(sc):  # type: (Text) -> Text
    sc = sc.replace("$job", "inputs")
    sc = sc.replace("$tmpdir", "runtime.tmpdir")
    sc = sc.replace("$outdir", "runtime.outdir")
    sc = sc.replace("$self", "self")
    return sc


def _updateDev2Script(ent):  # type: (Any) -> Any
    if isinstance(ent, dict) and "engine" in ent:
        if ent["engine"] == "https://w3id.org/cwl/cwl#JsonPointer":
            sp = ent["script"].split("/")
            if sp[0] in ("tmpdir", "outdir"):
                return u"$(runtime.%s)" % sp[0]
            else:
                if not sp[0]:
                    sp.pop(0)
                front = sp.pop(0)
                sp = [Text(i) if digits.match(i) else "'"+i+"'"
                      for i in sp]
                if front == "job":
                    return u"$(inputs[%s])" % ']['.join(sp)
                elif front == "context":
                    return u"$(self[%s])" % ']['.join(sp)
        else:
            sc = updateScript(ent["script"])
            if sc[0] == "{":
                return "$" + sc
            else:
                return u"$(%s)" % sc
    else:
        return ent


def _draftDraft3dev1toDev2(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    doc = _updateDev2Script(doc)
    if isinstance(doc, basestring):
        return doc

    # Convert expressions
    if isinstance(doc, dict):
        if "@import" in doc:
            resolved_doc = loader.resolve_ref(
                doc["@import"], base_url=baseuri)[0]
            if isinstance(resolved_doc, dict):
                return _draftDraft3dev1toDev2(
                    resolved_doc, loader, resolved_doc["id"])
            else:
                raise Exception("Unexpected codepath")

        for a in doc:
            doc[a] = _draftDraft3dev1toDev2(doc[a], loader, baseuri)

        if "class" in doc and (doc["class"] in ("CommandLineTool", "Workflow", "ExpressionTool")):
            added = False
            if "requirements" in doc:
                for r in doc["requirements"]:
                    if r["class"] == "ExpressionEngineRequirement":
                        if "engineConfig" in r:
                            doc["requirements"].append({
                                "class":"InlineJavascriptRequirement",
                                "expressionLib": [updateScript(sc) for sc in aslist(r["engineConfig"])]
                            })
                            added = True
                        for i, rq in enumerate(doc["requirements"]):
                            if rq["class"] == "ExpressionEngineRequirement":
                                del doc["requirements"][i]
                                break
                        break
            else:
                doc["requirements"] = []
            if not added:
                doc["requirements"].append({"class":"InlineJavascriptRequirement"})

    elif isinstance(doc, list):
        for i, a in enumerate(doc):
            doc[i] = _draftDraft3dev1toDev2(a, loader, baseuri)

    return doc


def draftDraft3dev1toDev2(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (_draftDraft3dev1toDev2(doc, loader, baseuri), "draft-3.dev2")

def _draftDraft3dev2toDev3(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    try:
        if isinstance(doc, dict):
            if "@import" in doc:
                if doc["@import"][0] == "#":
                    return doc["@import"]
                else:
                    imp = urlparse.urljoin(baseuri, doc["@import"])
                    impLoaded = loader.fetch(imp)
                    r = {}  # type: Dict[Text, Any]
                    if isinstance(impLoaded, list):
                        r = {"@graph": impLoaded}
                    elif isinstance(impLoaded, dict):
                        r = impLoaded
                    else:
                        raise Exception("Unexpected code path.")
                    r["id"] = imp
                    frag = urlparse.urldefrag(imp)[1]
                    if frag:
                        frag = "#" + frag
                        r = findId(r, frag)
                    return _draftDraft3dev2toDev3(r, loader, imp)

            if "@include" in doc:
                return loader.fetch_text(urlparse.urljoin(baseuri, doc["@include"]))

            for a in doc:
                doc[a] = _draftDraft3dev2toDev3(doc[a], loader, baseuri)

        if isinstance(doc, list):
            for i, a in enumerate(doc):
                doc[i] = _draftDraft3dev2toDev3(a, loader, baseuri)

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        import traceback
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))

def draftDraft3dev2toDev3(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (_draftDraft3dev2toDev3(doc, loader, baseuri), "draft-3.dev3")


def traverseImport(doc, loader, baseuri, func):
    # type: (Any, Loader, Text, Callable[[Any, Loader, Text], Any]) -> Any
    if "$import" in doc:
        if doc["$import"][0] == "#":
            return doc["$import"]
        else:
            imp = urlparse.urljoin(baseuri, doc["$import"])
            impLoaded = loader.fetch(imp)
            r = {}  # type: Dict[Text, Any]
            if isinstance(impLoaded, list):
                r = {"$graph": impLoaded}
            elif isinstance(impLoaded, dict):
                r = impLoaded
            else:
                raise Exception("Unexpected code path.")
            r["id"] = imp
            _, frag = urlparse.urldefrag(imp)
            if frag:
                frag = "#" + frag
                r = findId(r, frag)
            return func(r, loader, imp)


def _draftDraft3dev3toDev4(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    try:
        if isinstance(doc, dict):
            r = traverseImport(doc, loader, baseuri, _draftDraft3dev3toDev4)
            if r is not None:
                return r

            if "@graph" in doc:
                doc["$graph"] = doc["@graph"]
                del doc["@graph"]

            for a in doc:
                doc[a] = _draftDraft3dev3toDev4(doc[a], loader, baseuri)

        if isinstance(doc, list):
            for i, a in enumerate(doc):
                doc[i] = _draftDraft3dev3toDev4(a, loader, baseuri)

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        import traceback
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))


def draftDraft3dev3toDev4(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (_draftDraft3dev3toDev4(doc, loader, baseuri), "draft-3.dev4")

def _draftDraft3dev4toDev5(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    try:
        if isinstance(doc, dict):
            r = traverseImport(doc, loader, baseuri, _draftDraft3dev4toDev5)
            if r is not None:
                return r

            for b in ("inputBinding", "outputBinding"):
                if b in doc and "secondaryFiles" in doc[b]:
                    doc["secondaryFiles"] = doc[b]["secondaryFiles"]
                    del doc[b]["secondaryFiles"]

            for a in doc:
                doc[a] = _draftDraft3dev4toDev5(doc[a], loader, baseuri)

        if isinstance(doc, list):
            for i, a in enumerate(doc):
                doc[i] = _draftDraft3dev4toDev5(a, loader, baseuri)

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))


def draftDraft3dev4toDev5(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (_draftDraft3dev4toDev5(doc, loader, baseuri), "draft-3.dev5")

def draftDraft3dev5toFinal(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    return (doc, "draft-3")

def _draft3toDraft4dev1(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    if isinstance(doc, dict):
        if "class" in doc and doc["class"] == "Workflow":
            def fixup(f):  # type: (Text) -> Text
                doc, frg = urlparse.urldefrag(f)
                frg = '/'.join(frg.rsplit('.', 1))
                return doc + "#" + frg

            for step in doc["steps"]:
                step["in"] = step["inputs"]
                step["out"] = step["outputs"]
                del step["inputs"]
                del step["outputs"]
                for io in ("in", "out"):
                    for i in step[io]:
                        i["id"] = fixup(i["id"])
                        if "source" in i:
                            i["source"] = [fixup(s) for s in aslist(i["source"])]
                            if len(i["source"]) == 1:
                                i["source"] = i["source"][0]
                if "scatter" in step:
                    step["scatter"] = [fixup(s) for s in aslist(step["scatter"])]
            for out in doc["outputs"]:
                out["source"] = fixup(out["source"])
        for key, value in doc.items():
            doc[key] = _draft3toDraft4dev1(value, loader, baseuri)
    elif isinstance(doc, list):
        for i, a in enumerate(doc):
            doc[i] = _draft3toDraft4dev1(a, loader, baseuri)

    return doc

def draft3toDraft4dev1(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for draft-3 to draft-4.dev1."""
    return (_draft3toDraft4dev1(doc, loader, baseuri), "draft-4.dev1")

def _draft4Dev1toDev2(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    if isinstance(doc, dict):
        if "class" in doc and doc["class"] == "Workflow":
            for out in doc["outputs"]:
                out["outputSource"] = out["source"]
                del out["source"]
        for key, value in doc.items():
            doc[key] = _draft4Dev1toDev2(value, loader, baseuri)
    elif isinstance(doc, list):
        for i, a in enumerate(doc):
            doc[i] = _draft4Dev1toDev2(a, loader, baseuri)

    return doc

def draft4Dev1toDev2(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for draft-4.dev1 to draft-4.dev2."""
    return (_draft4Dev1toDev2(doc, loader, baseuri), "draft-4.dev2")


def _draft4Dev2toDev3(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    if isinstance(doc, dict):
        if "class" in doc and doc["class"] == "File":
            doc["location"] = doc["path"]
            del doc["path"]
        if "secondaryFiles" in doc:
            for i, sf in enumerate(doc["secondaryFiles"]):
                if "$(" in sf or "${" in sf:
                    doc["secondaryFiles"][i] = sf.replace('"path"', '"location"').replace(".path", ".location")

        if "class" in doc and doc["class"] == "CreateFileRequirement":
            doc["class"] = "InitialWorkDirRequirement"
            doc["listing"] = []
            for f in doc["fileDef"]:
                doc["listing"].append({
                    "entryname": f["filename"],
                    "entry": f["fileContent"]
                })
            del doc["fileDef"]
        for key, value in doc.items():
            doc[key] = _draft4Dev2toDev3(value, loader, baseuri)
    elif isinstance(doc, list):
        for i, a in enumerate(doc):
            doc[i] = _draft4Dev2toDev3(a, loader, baseuri)

    return doc

def draft4Dev2toDev3(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for draft-4.dev2 to draft-4.dev3."""
    return (_draft4Dev2toDev3(doc, loader, baseuri), "draft-4.dev3")

def _draft4Dev3to1_0dev4(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Any
    if isinstance(doc, dict):
        if "description" in doc:
            doc["doc"] = doc["description"]
            del doc["description"]
        for key, value in doc.items():
            doc[key] = _draft4Dev3to1_0dev4(value, loader, baseuri)
    elif isinstance(doc, list):
        for i, a in enumerate(doc):
            doc[i] = _draft4Dev3to1_0dev4(a, loader, baseuri)
    return doc

def draft4Dev3to1_0dev4(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for draft-4.dev3 to v1.0.dev4."""
    return (_draft4Dev3to1_0dev4(doc, loader, baseuri), "v1.0.dev4")

def v1_0dev4to1_0(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0.dev4 to v1.0."""
    return (doc, "v1.0")

def v1_0to1_1_0dev1(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0 to v1.1.0-dev1."""
    return (doc, "v1.1.0-dev1")


UPDATES = {
    "draft-2": draft2toDraft3dev1,
    "draft-3": draft3toDraft4dev1,
    "v1.0": None
}  # type: Dict[Text, Callable[[Any, Loader, Text], Tuple[Any, Text]]]

DEVUPDATES = {
    "draft-3.dev1": draftDraft3dev1toDev2,
    "draft-3.dev2": draftDraft3dev2toDev3,
    "draft-3.dev3": draftDraft3dev3toDev4,
    "draft-3.dev4": draftDraft3dev4toDev5,
    "draft-3.dev5": draftDraft3dev5toFinal,
    "draft-4.dev1": draft4Dev1toDev2,
    "draft-4.dev2": draft4Dev2toDev3,
    "draft-4.dev3": draft4Dev3to1_0dev4,
    "v1.0.dev4": v1_0dev4to1_0,
    "v1.0": v1_0to1_1_0dev1,
    "v1.1.0-dev1": None
}  # type: Dict[Text, Callable[[Any, Loader, Text], Tuple[Any, Text]]]

ALLUPDATES = UPDATES.copy()
ALLUPDATES.update(DEVUPDATES)

LATEST = "v1.0"

def identity(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Union[Text, Text]]
    """The default, do-nothing, CWL document upgrade function."""
    return (doc, doc["cwlVersion"])

def checkversion(doc, metadata, enable_dev):
    # type: (Union[CommentedSeq, CommentedMap], CommentedMap, bool) -> Tuple[Dict[Text, Any], Text]  # pylint: disable=line-too-long
    """Checks the validity of the version of the give CWL document.

    Returns the document and the validated version string.
    """

    cdoc = None  # type: CommentedMap
    if isinstance(doc, CommentedSeq):
        lc = metadata.lc
        metadata = copy.copy(metadata)
        metadata.lc.data = copy.copy(lc.data)
        metadata.lc.filename = lc.filename
        metadata[u"$graph"] = doc
        cdoc = metadata
    elif isinstance(doc, CommentedMap):
        cdoc = doc
    else:
        raise Exception("Expected CommentedMap or CommentedSeq")

    version = cdoc[u"cwlVersion"]

    if version not in UPDATES:
        if version in DEVUPDATES:
            if enable_dev:
                pass
            else:
                raise schema_salad.validate.ValidationException(
                    u"Version '%s' is a development or deprecated version.\n "
                    "Update your document to a stable version (%s) or use "
                    "--enable-dev to enable support for development and "
                    "deprecated versions." % (version, ", ".join(
                        UPDATES.keys())))
        else:
            raise schema_salad.validate.ValidationException(
                u"Unrecognized version %s" % version)

    return (cdoc, version)

def update(doc, loader, baseuri, enable_dev, metadata):
    # type: (Union[CommentedSeq, CommentedMap], Loader, Text, bool, Any) -> dict

    (cdoc, version) = checkversion(doc, metadata, enable_dev)

    nextupdate = identity  # type: Callable[[Any, Loader, Text], Tuple[Any, Text]]

    while nextupdate:
        (cdoc, version) = nextupdate(cdoc, loader, baseuri)
        nextupdate = ALLUPDATES[version]

    cdoc[u"cwlVersion"] = version

    return cdoc
