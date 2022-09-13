import copy
from functools import partial
from typing import (
    Callable,
    Dict,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import Loader
from schema_salad.sourceline import SourceLine

from .loghandler import _logger
from .utils import CWLObjectType, CWLOutputType, aslist, visit_class, visit_field


def v1_1to1_2(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.1 to v1.2."""
    doc = copy.deepcopy(doc)

    upd: Union[CommentedSeq, CommentedMap] = doc
    if isinstance(upd, MutableMapping) and "$graph" in upd:
        upd = upd["$graph"]
    for proc in aslist(upd):
        if "cwlVersion" in proc:
            del proc["cwlVersion"]

    return doc, "v1.2"


def v1_0to1_1(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
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

    def rewrite_requirements(t: CWLObjectType) -> None:
        if "requirements" in t:
            for r in cast(MutableSequence[CWLObjectType], t["requirements"]):
                if isinstance(r, MutableMapping):
                    cls = cast(str, r["class"])
                    if cls in rewrite:
                        r["class"] = rewrite[cls]
                else:
                    raise ValidationException(
                        "requirements entries must be dictionaries: {} {}.".format(
                            type(r), r
                        )
                    )
        if "hints" in t:
            for r in cast(MutableSequence[CWLObjectType], t["hints"]):
                if isinstance(r, MutableMapping):
                    cls = cast(str, r["class"])
                    if cls in rewrite:
                        r["class"] = rewrite[cls]
                else:
                    raise ValidationException(
                        f"hints entries must be dictionaries: {type(r)} {r}."
                    )
        if "steps" in t:
            for s in cast(MutableSequence[CWLObjectType], t["steps"]):
                if isinstance(s, MutableMapping):
                    rewrite_requirements(s)
                else:
                    raise ValidationException(
                        f"steps entries must be dictionaries: {type(s)} {s}."
                    )

    def update_secondaryFiles(t, top=False):
        # type: (CWLOutputType, bool) -> Union[MutableSequence[MutableMapping[str, str]], MutableMapping[str, str]]
        if isinstance(t, CommentedSeq):
            new_seq = copy.deepcopy(t)
            for index, entry in enumerate(t):
                new_seq[index] = update_secondaryFiles(entry)
            return new_seq
        elif isinstance(t, MutableSequence):
            return CommentedSeq(
                [update_secondaryFiles(cast(CWLOutputType, p)) for p in t]
            )
        elif isinstance(t, MutableMapping):
            return cast(MutableMapping[str, str], t)
        elif top:
            return CommentedSeq([CommentedMap([("pattern", t)])])
        else:
            return CommentedMap([("pattern", t)])

    def fix_inputBinding(t: CWLObjectType) -> None:
        for i in cast(MutableSequence[CWLObjectType], t["inputs"]):
            if "inputBinding" in i:
                ib = cast(CWLObjectType, i["inputBinding"])
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

    upd: Union[CommentedMap, CommentedSeq] = doc
    if isinstance(upd, MutableMapping) and "$graph" in upd:
        upd = upd["$graph"]
    for proc in aslist(upd):
        proc.setdefault("hints", CommentedSeq())
        na = CommentedMap([("class", "NetworkAccess"), ("networkAccess", True)])

        if hasattr(proc.lc, "filename"):
            comment_filename = proc.lc.filename
        else:
            comment_filename = ""
        na.lc.filename = comment_filename

        proc["hints"].insert(0, na)

        ll = CommentedMap(
            [("class", "LoadListingRequirement"), ("loadListing", "deep_listing")]
        )
        ll.lc.filename = comment_filename
        proc["hints"].insert(
            0,
            ll,
        )
        if "cwlVersion" in proc:
            del proc["cwlVersion"]

    return (doc, "v1.1")


def v1_1_0dev1to1_1(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.1.0-dev1 to v1.1."""
    return (doc, "v1.1")


def v1_2_0dev1todev2(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.2.0-dev1 to v1.2.0-dev2."""
    return (doc, "v1.2.0-dev2")


def v1_2_0dev2todev3(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.2.0-dev2 to v1.2.0-dev3."""
    doc = copy.deepcopy(doc)

    def update_pickvalue(t: CWLObjectType) -> None:
        for step in cast(MutableSequence[CWLObjectType], t["steps"]):
            for inp in cast(MutableSequence[CWLObjectType], step["in"]):
                if "pickValue" in inp:
                    if inp["pickValue"] == "only_non_null":
                        inp["pickValue"] = "the_only_non_null"

    visit_class(doc, "Workflow", update_pickvalue)
    upd: Union[CommentedSeq, CommentedMap] = doc
    if isinstance(upd, MutableMapping) and "$graph" in upd:
        upd = upd["$graph"]
    for proc in aslist(upd):
        if "cwlVersion" in proc:
            del proc["cwlVersion"]
    return (doc, "v1.2.0-dev3")


def v1_2_0dev3todev4(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.2.0-dev3 to v1.2.0-dev4."""
    return (doc, "v1.2.0-dev4")


def v1_2_0dev4todev5(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.2.0-dev4 to v1.2.0-dev5."""
    return (doc, "v1.2.0-dev5")


def v1_2_0dev5to1_2(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Public updater for v1.2.0-dev5 to v1.2."""
    return (doc, "v1.2")


ORDERED_VERSIONS = [
    "v1.0",
    "v1.1.0-dev1",
    "v1.1",
    "v1.2.0-dev1",
    "v1.2.0-dev2",
    "v1.2.0-dev3",
    "v1.2.0-dev4",
    "v1.2.0-dev5",
    "v1.2",
]

UPDATES = {
    "v1.0": v1_0to1_1,
    "v1.1": v1_1to1_2,
    "v1.2": None,
}  # type: Dict[str, Optional[Callable[[CommentedMap, Loader, str], Tuple[CommentedMap, str]]]]

DEVUPDATES = {
    "v1.1.0-dev1": v1_1_0dev1to1_1,
    "v1.2.0-dev1": v1_2_0dev1todev2,
    "v1.2.0-dev2": v1_2_0dev2todev3,
    "v1.2.0-dev3": v1_2_0dev3todev4,
    "v1.2.0-dev4": v1_2_0dev4todev5,
    "v1.2.0-dev5": v1_2_0dev5to1_2,
}  # type: Dict[str, Optional[Callable[[CommentedMap, Loader, str], Tuple[CommentedMap, str]]]]


ALLUPDATES = UPDATES.copy()
ALLUPDATES.update(DEVUPDATES)

INTERNAL_VERSION = "v1.2"

ORIGINAL_CWLVERSION = "http://commonwl.org/cwltool#original_cwlVersion"


def identity(
    doc: CommentedMap, loader: Loader, baseuri: str
) -> Tuple[CommentedMap, str]:  # pylint: disable=unused-argument
    """Do-nothing, CWL document upgrade function."""
    return (doc, cast(str, doc["cwlVersion"]))


def checkversion(
    doc: Union[CommentedSeq, CommentedMap],
    metadata: CommentedMap,
    enable_dev: bool,
) -> Tuple[CommentedMap, str]:
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

    updated_from = metadata.get(ORIGINAL_CWLVERSION) or cdoc.get(ORIGINAL_CWLVERSION)

    if updated_from:
        if version != INTERNAL_VERSION:
            raise ValidationException(
                "original_cwlVersion is set (%s) but cwlVersion is '%s', expected '%s' "
                % (updated_from, version, INTERNAL_VERSION)
            )
    elif version not in UPDATES:
        if version in DEVUPDATES:
            if enable_dev:
                pass
            else:
                keys = list(UPDATES.keys())
                keys.sort()
                raise ValidationException(
                    "Version '%s' is a development or deprecated version.\n "
                    "Update your document to a stable version (%s) or use "
                    "--enable-dev to enable support for development and "
                    "deprecated versions." % (version, ", ".join(keys))
                )
        else:
            raise ValidationException("Unrecognized version %s" % version)

    return (cdoc, version)


def update(
    doc: Union[CommentedSeq, CommentedMap],
    loader: Loader,
    baseuri: str,
    enable_dev: bool,
    metadata: CommentedMap,
    update_to: Optional[str] = None,
) -> CommentedMap:
    """Update a CWL document to 'update_to' (if provided) or INTERNAL_VERSION."""
    if update_to is None:
        update_to = INTERNAL_VERSION

    (cdoc, version) = checkversion(doc, metadata, enable_dev)
    originalversion = copy.copy(version)

    nextupdate = (
        identity
    )  # type: Optional[Callable[[CommentedMap, Loader, str], Tuple[CommentedMap, str]]]

    while version != update_to and nextupdate:
        (cdoc, version) = nextupdate(cdoc, loader, baseuri)
        nextupdate = ALLUPDATES[version]

    cdoc["cwlVersion"] = version
    metadata["cwlVersion"] = version
    metadata[ORIGINAL_CWLVERSION] = originalversion
    cdoc[ORIGINAL_CWLVERSION] = originalversion

    return cdoc
