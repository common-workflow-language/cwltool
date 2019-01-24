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
#LATEST = u"v1.1.0-dev1"


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
