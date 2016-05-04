import sys
import urlparse
import json
import re
from .utils import aslist
from typing import Any, Dict, Callable, List, Tuple, Union
import traceback
from schema_salad.ref_resolver import Loader

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
        return [fixType(f) for f in doc]

    if isinstance(doc, (str, unicode)):
        if doc not in ("null", "boolean", "int", "long", "float", "double", "string", "File", "record", "enum", "array", "Any") and "#" not in doc:
            return "#" + doc
    return doc

def _draft2toDraft3dev1(doc, loader, baseuri):  # type: (Any, Loader, str) -> Any
    try:
        if isinstance(doc, dict):
            if "import" in doc:
                imp = urlparse.urljoin(baseuri, doc["import"])
                impLoaded = loader.fetch(imp)
                r = None  # type: Dict[str, Any]
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

            for t in ("type", "items"):
                if t in doc:
                    doc[t] = fixType(doc[t])

            if "steps" in doc:
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
            return [_draft2toDraft3dev1(a, loader, baseuri) for a in doc]

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        import traceback
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))

def draft2toDraft3dev1(doc, loader, baseuri):  # type: (Any, Loader, str) -> Any
    return (_draft2toDraft3dev1(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev1")

digits = re.compile("\d+")

def updateScript(sc):  # type: (str) -> str
    sc = sc.replace("$job", "inputs")
    sc = sc.replace("$tmpdir", "runtime.tmpdir")
    sc = sc.replace("$outdir", "runtime.outdir")
    sc = sc.replace("$self", "self")
    return sc


def _updateDev2Script(ent):  # type: (Any) -> Any
    if isinstance(ent, dict) and "engine" in ent:
        if ent["engine"] == "cwl:JsonPointer":
            sp = ent["script"].split("/")
            if sp[0] in ("tmpdir", "outdir"):
                return u"$(runtime.%s)" % sp[0]
            else:
                if not sp[0]:
                    sp.pop(0)
                front = sp.pop(0)
                sp = [str(i) if digits.match(i) else "'"+i+"'"
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
    # type: (Any, Loader, str) -> Any
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
                        doc["requirements"] = [rq for rq in doc["requirements"] if rq["class"] != "ExpressionEngineRequirement"]
                        break
            else:
                doc["requirements"] = []
            if not added:
                doc["requirements"].append({"class":"InlineJavascriptRequirement"})

    elif isinstance(doc, list):
        return [_draftDraft3dev1toDev2(a, loader, baseuri) for a in doc]

    return doc


def draftDraft3dev1toDev2(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
    return (_draftDraft3dev1toDev2(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev2")

def _draftDraft3dev2toDev3(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
    try:
        if isinstance(doc, dict):
            if "@import" in doc:
                if doc["@import"][0] == "#":
                    return doc["@import"]
                else:
                    imp = urlparse.urljoin(baseuri, doc["@import"])
                    impLoaded = loader.fetch(imp)
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
            return [_draftDraft3dev2toDev3(a, loader, baseuri) for a in doc]

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
    # type: (Any, Loader, str) -> Any
    return (_draftDraft3dev2toDev3(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev3")


def traverseImport(doc, loader, baseuri, func):
    # type: (Any, Loader, str, Callable[[Any, Loader, str], Any]) -> Any
    if "$import" in doc:
        if doc["$import"][0] == "#":
            return doc["$import"]
        else:
            imp = urlparse.urljoin(baseuri, doc["$import"])
            impLoaded = loader.fetch(imp)
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
    # type: (Any, Loader, str) -> Any
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
            return [_draftDraft3dev3toDev4(a, loader, baseuri) for a in doc]

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
    # type: (Any, Loader, str) -> Any
    return (_draftDraft3dev3toDev4(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev4")

def _draftDraft3dev4toDev5(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
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
            return [_draftDraft3dev4toDev5(a, loader, baseuri) for a in doc]

        return doc
    except Exception as e:
        err = json.dumps(doc, indent=4)
        if "id" in doc:
            err = doc["id"]
        elif "name" in doc:
            err = doc["name"]
        raise Exception(u"Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc()))


def draftDraft3dev4toDev5(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
    return (_draftDraft3dev4toDev5(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev5")

def draftDraft3dev5toFinal(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
    return (doc, "https://w3id.org/cwl/cwl#draft-3")


def update(doc, loader, baseuri):
    # type: (Any, Loader, str) -> Any
    updates = {
        "https://w3id.org/cwl/cwl#draft-2": draft2toDraft3dev1,
        "https://w3id.org/cwl/cwl#draft-3.dev1": draftDraft3dev1toDev2,
        "https://w3id.org/cwl/cwl#draft-3.dev2": draftDraft3dev2toDev3,
        "https://w3id.org/cwl/cwl#draft-3.dev3": draftDraft3dev3toDev4,
        "https://w3id.org/cwl/cwl#draft-3.dev4": draftDraft3dev4toDev5,
        "https://w3id.org/cwl/cwl#draft-3.dev5": draftDraft3dev5toFinal,
        "https://w3id.org/cwl/cwl#draft-3": None
        }  # type: Dict[unicode, Any]

    def identity(doc, loader, baseuri):
        # type: (Any, Loader, str) -> Tuple[Any, Union[str, unicode]]
        v = doc.get("cwlVersion")
        if v:
            return (doc, loader.expand_url(v, ""))
        else:
            return (doc, "https://w3id.org/cwl/cwl#draft-2")

    nextupdate = identity

    while nextupdate:
        (doc, version) = nextupdate(doc, loader, baseuri)
        if version in updates:
            nextupdate = updates[version]
        else:
            raise Exception(u"Unrecognized version %s" % version)

    doc["cwlVersion"] = version

    return doc
