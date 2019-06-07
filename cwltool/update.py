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
from schema_salad.sourceline import SourceLine
from .loghandler import _logger

# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .utils import visit_class, visit_field, aslist


def v1_0to1_1(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Text]
    """Public updater for v1.0 to v1.1."""
    doc = copy.deepcopy(doc)

    rewrite = {
        "http://commonwl.org/cwltool#WorkReuse": "WorkReuse",
        "http://arvados.org/cwl#ReuseRequirement": "WorkReuse",
        "http://commonwl.org/cwltool#TimeLimit": "ToolTimeLimit",
        "http://commonwl.org/cwltool#NetworkAccess": "NetworkAccess",
        "http://commonwl.org/cwltool#InplaceUpdateRequirement": "InplaceUpdateRequirement",
        "http://commonwl.org/cwltool#LoadListingRequirement": "LoadListingRequirement"
    }
    def rewrite_requirements(t):
        if "requirements" in t:
            for r in t["requirements"]:
                if r["class"] in rewrite:
                    r["class"] = rewrite[r["class"]]
        if "hints" in t:
            for r in t["hints"]:
                if r["class"] in rewrite:
                    r["class"] = rewrite[r["class"]]
        if "steps" in t:
            for s in t["steps"]:
                rewrite_requirements(s)

    def update_secondaryFiles(t):
        if isinstance(t, MutableSequence):
            return [update_secondaryFiles(p) for p in t]
        elif isinstance(t, MutableMapping):
            return t
        else:
            return {"pattern": t}

    def fix_inputBinding(t):
        for i in t["inputs"]:
            if "inputBinding" in i:
                ib = i["inputBinding"]
                for k in list(ib.keys()):
                    if k != "loadContents":
                        _logger.warning(SourceLine(ib, k).makeError("Will ignore field '%s' which is not valid in %s inputBinding" %
                                                                    (k, t["class"])))
                        del ib[k]

    visit_class(doc, ("CommandLineTool","Workflow"), rewrite_requirements)
    visit_class(doc, ("ExpressionTool","Workflow"), fix_inputBinding)
    visit_field(doc, "secondaryFiles", update_secondaryFiles)

    upd = doc
    if isinstance(upd, MutableMapping) and "$graph" in upd:
        upd = upd["$graph"]
    for proc in aslist(upd):
        proc.setdefault("hints", [])
        proc["hints"].insert(0, {"class": "NetworkAccess", "networkAccess": True})
        proc["hints"].insert(0, {"class": "LoadListingRequirement", "loadListing": "deep_listing"})
        if "cwlVersion" in proc:
            del proc["cwlVersion"]

    return (doc, "v1.1")

def v1_1_0dev1to1_1(doc, loader, baseuri):  # pylint: disable=unused-argument
    return (doc, "v1.1")

UPDATES = {
    u"v1.0": v1_0to1_1,
    u"v1.1": None
}  # type: Dict[Text, Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]]

DEVUPDATES = {
    u"v1.0": v1_0to1_1,
    u"v1.1.0-dev1": v1_1_0dev1to1_1,
    u"v1.1": None
}  # type: Dict[Text, Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]]

ALLUPDATES = UPDATES.copy()
ALLUPDATES.update(DEVUPDATES)

INTERNAL_VERSION = u"v1.1"

def identity(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, Text) -> Tuple[Any, Union[Text, Text]]
    """Default, do-nothing, CWL document upgrade function."""
    return (doc, doc["cwlVersion"])


def checkversion(doc,        # type: Union[CommentedSeq, CommentedMap]
                 metadata,   # type: CommentedMap
                 enable_dev  # type: bool
):
    # type: (...) -> Tuple[Union[CommentedSeq, CommentedMap], Text]
    """Check the validity of the version of the give CWL document.

    Returns the document and the validated version string.
    """
    cdoc = None  # type: Optional[CommentedMap]
    if isinstance(doc, CommentedSeq):
        if not isinstance(metadata, CommentedMap):
            raise Exception("Expected metadata to be CommentedMap")
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

    version = metadata[u"cwlVersion"]
    cdoc["cwlVersion"] = version

    if version not in UPDATES:
        if version in DEVUPDATES:
            if enable_dev:
                pass
            else:
                keys = list(UPDATES.keys())
                keys.sort()
                raise validate.ValidationException(
                    u"Version '%s' is a development or deprecated version.\n "
                    "Update your document to a stable version (%s) or use "
                    "--enable-dev to enable support for development and "
                    "deprecated versions." % (version, ", ".join(keys)))
        else:
            raise validate.ValidationException(
                u"Unrecognized version %s" % version)

    return (cdoc, version)


def update(doc, loader, baseuri, enable_dev, metadata):
    # type: (Union[CommentedSeq, CommentedMap], Loader, Text, bool, Any) -> Union[CommentedSeq, CommentedMap]

    if (metadata.get("http://commonwl.org/cwltool#original_cwlVersion") or
        (isinstance(doc, CommentedMap) and doc.get("http://commonwl.org/cwltool#original_cwlVersion"))):
        return doc

    (cdoc, originalversion) = checkversion(doc, metadata, enable_dev)
    version = originalversion

    (cdoc, version) = checkversion(doc, metadata, enable_dev)

    nextupdate = identity  # type: Optional[Callable[[Any, Loader, Text], Tuple[Any, Text]]]

    while nextupdate:
        (cdoc, version) = nextupdate(cdoc, loader, baseuri)
        nextupdate = ALLUPDATES[version]

    cdoc[u"cwlVersion"] = version
    metadata[u"cwlVersion"] = version
    metadata[u"http://commonwl.org/cwltool#original_cwlVersion"] = originalversion
    cdoc[u"http://commonwl.org/cwltool#original_cwlVersion"] = originalversion

    return cdoc
