from __future__ import absolute_import
import copy
import json
import re
import traceback
from typing import (Any, Callable, Dict, Text,  # pylint: disable=unused-import
                    Tuple, Union)
from copy import deepcopy

import six
from six.moves import urllib
import schema_salad.validate
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.ref_resolver import Loader

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
                sp = [Text(i) if digits.match(i) else "'" + i + "'"
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

def traverseImport(doc, loader, baseuri, func):
    # type: (Any, Loader, Text, Callable[[Any, Loader, Text], Any]) -> Any
    if "$import" in doc:
        if doc["$import"][0] == "#":
            return doc["$import"]
        else:
            imp = urllib.parse.urljoin(baseuri, doc["$import"])
            impLoaded = loader.fetch(imp)
            r = {}  # type: Dict[Text, Any]
            if isinstance(impLoaded, list):
                r = {"$graph": impLoaded}
            elif isinstance(impLoaded, dict):
                r = impLoaded
            else:
                raise Exception("Unexpected code path.")
            r["id"] = imp
            _, frag = urllib.parse.urldefrag(imp)
            if frag:
                frag = "#" + frag
                r = findId(r, frag)
            return func(r, loader, imp)

def v1_0dev4to1_0(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0.dev4 to v1.0."""
    return (doc, "v1.0")


def v1_0to1_1_0dev1(doc, loader, baseuri):
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0 to v1.1.0-dev1."""
    return (doc, "v1.1.0-dev1")


UPDATES = {
    "v1.0": None
}  # type: Dict[Text, Callable[[Any, Loader, Text], Tuple[Any, Text]]]

DEVUPDATES = {
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
                        list(UPDATES.keys()))))
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
