import copy
import re
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad import validate
from schema_salad.ref_resolver import Loader
from schema_salad.sourceline import SourceLine

from .loghandler import _logger
from .utils import aslist, visit_class, visit_field


def v1_0to1_1(
    doc: Any, loader: Loader, baseuri: str
) -> Tuple[Any, str]:  # pylint: disable=unused-argument
    """Public updater for v1.0 to v1.1."""
    doc = copy.deepcopy(doc)

    rewrite = {
        "http://commonwl.org/cwltool#WorkReuse": "WorkReuse",
        "http://arvados.org/cwl#ReuseRequirement": "WorkReuse",
        "http://commonwl.org/cwltool#TimeLimit": "ToolTimeLimit",
        "http://commonwl.org/cwltool#NetworkAccess": "NetworkAccess",
        "http://commonwl.org/cwltool#InplaceUpdateRequirement": "InplaceUpdateRequirement",
        "http://commonwl.org/cwltool#LoadListingRequirement": "LoadListingRequirement",
    }

    def rewrite_requirements(
        t: MutableMapping[str, Union[str, Dict[str, Any]]]
    ) -> None:
        if "requirements" in t:
            for r in t["requirements"]:
                if isinstance(r, MutableMapping):
                    if r["class"] in rewrite:
                        r["class"] = rewrite[r["class"]]
                else:
                    raise validate.ValidationException(
                        "requirements entries must be dictionaries: {} {}.".format(
                            type(r), r
                        )
                    )
        if "hints" in t:
            for r in t["hints"]:
                if isinstance(r, MutableMapping):
                    if r["class"] in rewrite:
                        r["class"] = rewrite[r["class"]]
                else:
                    raise validate.ValidationException(
                        "hints entries must be dictionaries: {} {}.".format(type(r), r)
                    )
        if "steps" in t:
            for s in t["steps"]:
                if isinstance(s, MutableMapping):
                    rewrite_requirements(s)
                else:
                    raise validate.ValidationException(
                        "steps entries must be dictionaries: {} {}.".format(type(s), s)
                    )

    def update_secondaryFiles(t, top=False):
        # type: (Any, bool) -> Union[MutableSequence[MutableMapping[str, str]], MutableMapping[str, str]]
        if isinstance(t, CommentedSeq):
            new_seq = copy.deepcopy(t)
            for index, entry in enumerate(t):
                new_seq[index] = update_secondaryFiles(entry)
            return new_seq
        elif isinstance(t, MutableSequence):
            return CommentedSeq([update_secondaryFiles(p) for p in t])
        elif isinstance(t, MutableMapping):
            return t
        elif top:
            return CommentedSeq([CommentedMap([("pattern", t)])])
        else:
            return CommentedMap([("pattern", t)])

    def fix_inputBinding(t):  # type: (Dict[str, Any]) -> None
        for i in t["inputs"]:
            if "inputBinding" in i:
                ib = i["inputBinding"]
                for k in list(ib.keys()):
                    if k != "loadContents":
                        _logger.warning(
                            SourceLine(ib, k).makeError(
                                "Will ignore field '{}' which is not valid in {} "
                                "inputBinding".format(k, t["class"])
                            )
                        )
                        del ib[k]

    visit_class(doc, ("CommandLineTool", "Workflow"), rewrite_requirements)
    visit_class(doc, ("ExpressionTool", "Workflow"), fix_inputBinding)
    visit_field(doc, "secondaryFiles", partial(update_secondaryFiles, top=True))

    upd = doc
    if isinstance(upd, MutableMapping) and "$graph" in upd:
        upd = upd["$graph"]
    for proc in aslist(upd):
        proc.setdefault("hints", CommentedSeq())
        proc["hints"].insert(
            0, CommentedMap([("class", "NetworkAccess"), ("networkAccess", True)])
        )
        proc["hints"].insert(
            0,
            CommentedMap(
                [("class", "LoadListingRequirement"), ("loadListing", "deep_listing")]
            ),
        )
        if "cwlVersion" in proc:
            del proc["cwlVersion"]

    return (doc, "v1.1")


def v1_1_0dev1to1_1(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, str) -> Tuple[Any, str]
    return (doc, "v1.1")


UPDATES = {
    "v1.0": v1_0to1_1,
    "v1.1": None,
}  # type: Dict[str, Optional[Callable[[Any, Loader, str], Tuple[Any, str]]]]

DEVUPDATES = {
    "v1.0": v1_0to1_1,
    "v1.1.0-dev1": v1_1_0dev1to1_1,
    "v1.1": None,
}  # type: Dict[str, Optional[Callable[[Any, Loader, str], Tuple[Any, str]]]]

ALLUPDATES = UPDATES.copy()
ALLUPDATES.update(DEVUPDATES)

INTERNAL_VERSION = "v1.1"


def identity(doc, loader, baseuri):  # pylint: disable=unused-argument
    # type: (Any, Loader, str) -> Tuple[Any, Union[str, str]]
    """Default, do-nothing, CWL document upgrade function."""
    return (doc, doc["cwlVersion"])


def checkversion(
    doc,  # type: Union[CommentedSeq, CommentedMap]
    metadata,  # type: CommentedMap
    enable_dev,  # type: bool
):
    # type: (...) -> Tuple[CommentedMap, str]
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
        metadata["$graph"] = doc
        cdoc = metadata
    elif isinstance(doc, CommentedMap):
        cdoc = doc
    else:
        raise Exception("Expected CommentedMap or CommentedSeq")

    version = metadata["cwlVersion"]
    cdoc["cwlVersion"] = version

    if version not in UPDATES:
        if version in DEVUPDATES:
            if enable_dev:
                pass
            else:
                keys = list(UPDATES.keys())
                keys.sort()
                raise validate.ValidationException(
                    "Version '%s' is a development or deprecated version.\n "
                    "Update your document to a stable version (%s) or use "
                    "--enable-dev to enable support for development and "
                    "deprecated versions." % (version, ", ".join(keys))
                )
        else:
            raise validate.ValidationException("Unrecognized version %s" % version)

    return (cdoc, version)


def update(doc, loader, baseuri, enable_dev, metadata):
    # type: (Union[CommentedSeq, CommentedMap], Loader, str, bool, Any) -> CommentedMap

    if isinstance(doc, CommentedMap):
        if metadata.get("http://commonwl.org/cwltool#original_cwlVersion") or doc.get(
            "http://commonwl.org/cwltool#original_cwlVersion"
        ):
            return doc

    (cdoc, version) = checkversion(doc, metadata, enable_dev)
    originalversion = copy.copy(version)

    nextupdate = (
        identity
    )  # type: Optional[Callable[[Any, Loader, str], Tuple[Any, str]]]

    while nextupdate:
        (cdoc, version) = nextupdate(cdoc, loader, baseuri)
        nextupdate = ALLUPDATES[version]

    cdoc["cwlVersion"] = version
    metadata["cwlVersion"] = version
    metadata["http://commonwl.org/cwltool#original_cwlVersion"] = originalversion
    cdoc["http://commonwl.org/cwltool#original_cwlVersion"] = originalversion

    return cdoc
