import sys
import urlparse
import json
import re
from aslist import aslist

def findId(doc, frg):
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

def fixType(doc):
    if isinstance(doc, list):
        return [fixType(f) for f in doc]

    if isinstance(doc, basestring):
        if doc not in ("null", "boolean", "int", "long", "float", "double", "string", "File", "record", "enum", "array", "Any") and "#" not in doc:
            return "#" + doc
    return doc

def _draft2toDraft3dev1(doc, loader, baseuri):
    try:
        if isinstance(doc, dict):
            if "import" in doc:
                imp = urlparse.urljoin(baseuri, doc["import"])
                r = loader.fetch(imp)
                if isinstance(r, list):
                    r = {"@graph": r}
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
        raise Exception("Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc(e)))

def draft2toDraft3dev1(doc, loader, baseuri):
    return (_draft2toDraft3dev1(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev1")

digits = re.compile("\d+")

def updateScript(sc):
    sc = sc.replace("$job", "inputs")
    sc = sc.replace("$tmpdir", "runtime.tmpdir")
    sc = sc.replace("$outdir", "runtime.outdir")
    sc = sc.replace("$self", "self")
    return sc

def _updateDev2Script(ent):
    if isinstance(ent, dict) and "engine" in ent:
        if ent["engine"] == "cwl:JsonPointer":
            sp = ent["script"].split("/")
            if sp[0] in ("tmpdir", "outdir"):
                return "$(runtime.%s)" % sp[0]
            else:
                if not sp[0]:
                    sp.pop(0)
                front = sp.pop(0)
                sp = [str(i) if digits.match(i) else "'"+i+"'"
                      for i in sp]
                if front == "job":
                    return "$(inputs[%s])" % ']['.join(sp)
                elif front == "context":
                    return "$(self[%s])" % ']['.join(sp)
        else:
            sc = updateScript(ent["script"])
            if sc[0] == "{":
                return "$" + sc
            else:
                return "$(%s)" % sc
    else:
        return ent

def _draftDraft3dev1toDev2(doc, loader, baseuri):
    doc = _updateDev2Script(doc)
    if isinstance(doc, basestring):
        return doc

    # Convert expressions
    if isinstance(doc, dict):
        if "@import" in doc:
            r, _ = loader.resolve_ref(doc["@import"], base_url=baseuri)
            return _draftDraft3dev1toDev2(r, loader, r["id"])

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
    return (_draftDraft3dev1toDev2(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev2")

def _draftDraft3dev2toDev3(doc, loader, baseuri):
    try:
        if isinstance(doc, dict):
            if "@import" in doc:
                if doc["@import"][0] == "#":
                    return doc["@import"]
                else:
                    imp = urlparse.urljoin(baseuri, doc["@import"])
                    r = loader.fetch(imp)
                    if isinstance(r, list):
                        r = {"@graph": r}
                    r["id"] = imp
                    _, frag = urlparse.urldefrag(imp)
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
        raise Exception("Error updating '%s'\n  %s\n%s" % (err, e, traceback.format_exc(e)))

def draftDraft3dev2toDev3(doc, loader, baseuri):
    return (_draftDraft3dev2toDev3(doc, loader, baseuri), "https://w3id.org/cwl/cwl#draft-3.dev3")


def update(doc, loader, baseuri):
    updates = {
        "https://w3id.org/cwl/cwl#draft-2": draft2toDraft3dev1,
        "https://w3id.org/cwl/cwl#draft-3.dev1": draftDraft3dev1toDev2,
        "https://w3id.org/cwl/cwl#draft-3.dev2": draftDraft3dev2toDev3,
        "https://w3id.org/cwl/cwl#draft-3.dev3": None
    }

    def identity(doc, loader, baseuri):
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
            raise Exception("Unrecognized version %s" % version)

    doc["cwlVersion"] = version

    return doc
