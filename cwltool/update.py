from __future__ import absolute_import

import copy
import re
from typing import (Any, Callable, Dict, MutableMapping, MutableSequence,
                    Optional, Tuple, Union)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad import validate
from schema_salad.ref_resolver import Loader  # pylint: disable=unused-import
from six import string_types
from six.moves import urllib
from typing_extensions import Text
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .utils import visit_class


def find_id(doc, frg):  # type: (Any, Any) -> Optional[MutableMapping]
    if isinstance(doc, MutableMapping):
        if "id" in doc and doc["id"] == frg:
            return doc
        for key in doc:
            found = find_id(doc[key], frg)
            if found:
                return found
    if isinstance(doc, MutableSequence):
        for entry in doc:
            found = find_id(entry, frg)
            if found:
                return found
    return None


def fixType(doc):  # type: (Any) -> Any
    if isinstance(doc, MutableSequence):
        for i, f in enumerate(doc):
            doc[i] = fixType(f)
        return doc

    if isinstance(doc, string_types):
        if doc not in (
                "null", "boolean", "int", "long", "float", "double", "string",
                "File", "record", "enum", "array", "Any") and "#" not in doc:
            return "#" + doc
    return doc

digits = re.compile(r"\d+")


def updateScript(sc):  # type: (Text) -> Text
    sc = sc.replace("$job", "inputs")
    sc = sc.replace("$tmpdir", "runtime.tmpdir")
    sc = sc.replace("$outdir", "runtime.outdir")
    sc = sc.replace("$self", "self")
    return sc


def _updateDev2Script(ent):  # type: (Any) -> Any
    if isinstance(ent, MutableMapping) and "engine" in ent:
        if ent["engine"] == "https://w3id.org/cwl/cwl#JsonPointer":
            sp = ent["script"].split("/")
            if sp[0] in ("tmpdir", "outdir"):
                return u"$(runtime.%s)" % sp[0]
            if not sp[0]:
                sp.pop(0)
            front = sp.pop(0)
            sp = [Text(i) if digits.match(i) else "'" + i + "'"
                  for i in sp]
            if front == "job":
                return u"$(inputs[%s])" % ']['.join(sp)
            if front == "context":
                return u"$(self[%s])" % ']['.join(sp)
        else:
            sc = updateScript(ent["script"])
            if sc[0] == "{":
                return "$" + sc
            return u"$(%s)" % sc
    return ent

def traverseImport(doc, loader, baseuri, func):
    # type: (Any, Loader, Text, Callable[[Any, Loader, Text], Any]) -> Any
    if "$import" in doc:
        if doc["$import"][0] == "#":
            return doc["$import"]
        imp = urllib.parse.urljoin(baseuri, doc["$import"])
        impLoaded = loader.fetch(imp)
        r = {}  # type: MutableMapping[Text, Any]
        if isinstance(impLoaded, MutableSequence):
            r = {"$graph": impLoaded}
        elif isinstance(impLoaded, MutableMapping):
            r = impLoaded
        else:
            raise Exception("Unexpected code path.")
        r["id"] = imp
        _, frag = urllib.parse.urldefrag(imp)
        if frag:
            frag = "#" + frag
            r = find_id(r, frag)  # type: ignore
        return func(r, loader, imp)

def v1_0dev4to1_0(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0.dev4 to v1.0."""
    return (doc, "v1.0")


def v1_0to1_1_0dev1(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0 to v1.1.0-dev1."""

    def add_networkaccess(t):
        t.setdefault("requirements", [])
        t["requirements"].append({
            "class": "NetworkAccess",
            "networkAccess": True
            })

    visit_class(doc, ("CommandLineTool",), add_networkaccess)

    return (doc, "v1.1.0-dev1")


UPDATES = {
    u"v1.0": None
}  # type: Dict[Text, Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]]

DEVUPDATES = {
    u"v1.0": v1_0to1_1_0dev1,
    u"v1.1.0-dev1": None
}  # type: Dict[Text, Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]]

ALLUPDATES = UPDATES.copy()
ALLUPDATES.update(DEVUPDATES)

LATEST = u"v1.0"


def identity(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Union[Text, Text]]
    """The default, do-nothing, CWL document upgrade function."""
    return (doc, doc["cwlVersion"])


def checkversion(doc, metadata, enable_dev):
    # type: (Union[CommentedSeq, CommentedMap], CommentedMap, bool) -> Tuple[Dict[Text, Any], Text]  # pylint: disable=line-too-long
    """Checks the validity of the version of the give CWL document.

    Returns the document and the validated version string.
    """

    cdoc = None  # type: Optional[CommentedMap]
    if isinstance(doc, CommentedSeq):
        lc = metadata.lc
        metadata = copy.deepcopy(metadata)
        metadata.lc.data = copy.copy(lc.data)
        metadata.lc.filename = lc.filename
        metadata[u"$graph"] = doc
        cdoc = metadata
    elif isinstance(doc, CommentedMap):
        cdoc = doc
    else:
        raise Exception("Expected CommentedMap or CommentedSeq")
    assert cdoc is not None

    version = cdoc[u"cwlVersion"]

    if version not in UPDATES:
        if version in DEVUPDATES:
            if enable_dev:
                pass
            else:
                raise validate.ValidationException(
                    u"Version '%s' is a development or deprecated version.\n "
                    "Update your document to a stable version (%s) or use "
                    "--enable-dev to enable support for development and "
                    "deprecated versions." % (version, ", ".join(
                        list(UPDATES.keys()))))
        else:
            raise validate.ValidationException(
                u"Unrecognized version %s" % version)

    return (cdoc, version)


def update(doc, loader, baseuri, enable_dev, metadata):
    # type: (Union[CommentedSeq, CommentedMap], Loader, Text, bool, Any) -> dict

    (cdoc, version) = checkversion(doc, metadata, enable_dev)

    nextupdate = identity  # type: Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]

    while nextupdate:
        (cdoc, version) = nextupdate(cdoc, loader, baseuri)
        nextupdate = ALLUPDATES[version]

    cdoc[u"cwlVersion"] = version

    return cdoc
