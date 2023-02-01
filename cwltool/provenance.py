"""
Stores Research Object including provenance.

See :doc:`/CWLProv`
"""

import copy
import datetime
import hashlib
import os
import pwd
import re
import shutil
import tempfile
import uuid
from array import array
from collections import OrderedDict
from getpass import getuser
from io import FileIO, TextIOWrapper
from mmap import mmap
from pathlib import Path, PurePosixPath
from typing import (
    IO,
    Any,
    BinaryIO,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import prov.model as provM
from prov.model import PROV, ProvDocument
from schema_salad.utils import json_dumps
from typing_extensions import TypedDict

from .loghandler import _logger
from .provenance_constants import (
    ACCOUNT_UUID,
    CWLPROV,
    CWLPROV_VERSION,
    DATA,
    ENCODING,
    FOAF,
    LOGS,
    METADATA,
    ORCID,
    PROVENANCE,
    SHA1,
    SHA256,
    SHA512,
    SNAPSHOT,
    TEXT_PLAIN,
    USER_UUID,
    UUID,
    WORKFLOW,
    Hasher,
)
from .stdfsaccess import StdFsAccess
from .utils import (
    CWLObjectType,
    CWLOutputType,
    create_tmp_dir,
    local_path,
    posix_path,
    versionstring,
)


def _whoami() -> Tuple[str, str]:
    """Return the current operating system account as (username, fullname)."""
    username = getuser()
    try:
        fullname = pwd.getpwuid(os.getuid())[4].split(",")[0]
    except (KeyError, IndexError):
        fullname = username

    return (username, fullname)


class WritableBagFile(FileIO):
    """Writes files in research object."""

    def __init__(self, research_object: "ResearchObject", rel_path: str) -> None:
        """Initialize an ROBagIt."""
        self.research_object = research_object
        if Path(rel_path).is_absolute():
            raise ValueError("rel_path must be relative: %s" % rel_path)
        self.rel_path = rel_path
        self.hashes = {
            SHA1: hashlib.sha1(),  # nosec
            SHA256: hashlib.sha256(),
            SHA512: hashlib.sha512(),
        }
        # Open file in Research Object folder
        path = os.path.abspath(os.path.join(research_object.folder, local_path(rel_path)))
        if not path.startswith(os.path.abspath(research_object.folder)):
            raise ValueError("Path is outside Research Object: %s" % path)
        _logger.debug("[provenance] Creating WritableBagFile at %s.", path)
        super().__init__(path, mode="w")

    def write(self, b: Any) -> int:
        """Write some content to the Bag."""
        real_b = b if isinstance(b, (bytes, mmap, array)) else b.encode("utf-8")
        total = 0
        length = len(real_b)
        while total < length:
            ret = super().write(real_b)
            if ret:
                total += ret
        for val in self.hashes.values():
            # print("Updating hasher %s ", val)
            val.update(real_b)
        return total

    def close(self) -> None:
        # FIXME: Convert below block to a ResearchObject method?
        if self.rel_path.startswith("data/"):
            self.research_object.bagged_size[self.rel_path] = self.tell()
        else:
            self.research_object.tagfiles.add(self.rel_path)

        super().close()
        # { "sha1": "f572d396fae9206628714fb2ce00f72e94f2258f" }
        checksums = {}
        for name in self.hashes:
            checksums[name] = self.hashes[name].hexdigest().lower()
        self.research_object.add_to_manifest(self.rel_path, checksums)

    # To simplify our hash calculation we won't support
    # seeking, reading or truncating, as we can't do
    # similar seeks in the current hash.
    # TODO: Support these? At the expense of invalidating
    # the current hash, then having to recalculate at close()
    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def truncate(self, size: Optional[int] = None) -> int:
        # FIXME: This breaks contract IOBase,
        # as it means we would have to recalculate the hash
        if size is not None:
            raise OSError("WritableBagFile can't truncate")
        return self.tell()


def _check_mod_11_2(numeric_string: str) -> bool:
    """
    Validate numeric_string for its MOD-11-2 checksum.

    Any "-" in the numeric_string are ignored.

    The last digit of numeric_string is assumed to be the checksum, 0-9 or X.

    See ISO/IEC 7064:2003 and
    https://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier
    """
    # Strip -
    nums = numeric_string.replace("-", "")
    total = 0
    # skip last (check)digit
    for num in nums[:-1]:
        digit = int(num)
        total = (total + digit) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    if result == 10:
        checkdigit = "X"
    else:
        checkdigit = str(result)
    # Compare against last digit or X
    return nums[-1].upper() == checkdigit


def _valid_orcid(orcid: Optional[str]) -> str:
    """
    Ensure orcid is a valid ORCID identifier.

    The string must be equivalent to one of these forms:

    0000-0002-1825-0097
    orcid.org/0000-0002-1825-0097
    http://orcid.org/0000-0002-1825-0097
    https://orcid.org/0000-0002-1825-0097

    If the ORCID number or prefix is invalid, a ValueError is raised.

    The returned ORCID string is always in the form of:
    https://orcid.org/0000-0002-1825-0097
    """
    if orcid is None or not orcid:
        raise ValueError("ORCID cannot be unspecified")
    # Liberal in what we consume, e.g. ORCID.org/0000-0002-1825-009x
    orcid = orcid.lower()
    match = re.match(
        # Note: concatenated r"" r"" below so we can add comments to pattern
        # Optional hostname, with or without protocol
        r"(http://orcid\.org/|https://orcid\.org/|orcid\.org/)?"
        # alternative pattern, but probably messier
        # r"^((https?://)?orcid.org/)?"
        # ORCID number is always 4x4 numerical digits,
        # but last digit (modulus 11 checksum)
        # can also be X (but we made it lowercase above).
        # e.g. 0000-0002-1825-0097
        # or   0000-0002-1694-233x
        r"(?P<orcid>(\d{4}-\d{4}-\d{4}-\d{3}[0-9x]))$",
        orcid,
    )

    help_url = (
        "https://support.orcid.org/knowledgebase/articles/"
        "116780-structure-of-the-orcid-identifier"
    )
    if not match:
        raise ValueError(f"Invalid ORCID: {orcid}\n{help_url}")

    # Conservative in what we produce:
    # a) Ensure any checksum digit is uppercase
    orcid_num = match.group("orcid").upper()
    # b) ..and correct
    if not _check_mod_11_2(orcid_num):
        raise ValueError(f"Invalid ORCID checksum: {orcid_num}\n{help_url}")

    # c) Re-add the official prefix https://orcid.org/
    return "https://orcid.org/%s" % orcid_num


Annotation = TypedDict(
    "Annotation",
    {
        "uri": str,
        "about": str,
        "content": Optional[Union[str, List[str]]],
        "oa:motivatedBy": Dict[str, str],
    },
)
Aggregate = TypedDict(
    "Aggregate",
    {
        "uri": Optional[str],
        "bundledAs": Optional[Dict[str, Any]],
        "mediatype": Optional[str],
        "conformsTo": Optional[Union[str, List[str]]],
        "createdOn": Optional[str],
        "createdBy": Optional[Dict[str, str]],
    },
    total=False,
)
# Aggregate.bundledAs is actually type Aggregate, but cyclic definitions are not supported
AuthoredBy = TypedDict(
    "AuthoredBy",
    {"orcid": Optional[str], "name": Optional[str], "uri": Optional[str]},
    total=False,
)


class ResearchObject:
    """CWLProv Research Object."""

    def __init__(
        self,
        fsaccess: StdFsAccess,
        temp_prefix_ro: str = "tmp",
        orcid: str = "",
        full_name: str = "",
    ) -> None:
        """Initialize the ResearchObject."""
        self.temp_prefix = temp_prefix_ro
        self.orcid = "" if not orcid else _valid_orcid(orcid)
        self.full_name = full_name
        self.folder = create_tmp_dir(temp_prefix_ro)
        self.closed = False
        # map of filename "data/de/alsdklkas": 12398123 bytes
        self.bagged_size: Dict[str, int] = {}
        self.tagfiles: Set[str] = set()
        self._file_provenance: Dict[str, Aggregate] = {}
        self._external_aggregates: List[Aggregate] = []
        self.annotations: List[Annotation] = []
        self._content_types: Dict[str, str] = {}
        self.fsaccess = fsaccess
        # These should be replaced by generate_prov_doc when workflow/run IDs are known:
        self.engine_uuid = "urn:uuid:%s" % uuid.uuid4()
        self.ro_uuid = uuid.uuid4()
        self.base_uri = "arcp://uuid,%s/" % self.ro_uuid
        self.cwltool_version = "cwltool %s" % versionstring().split()[-1]
        ##
        self.relativised_input_object: CWLObjectType = {}
        self.has_manifest = False

        self._initialize()
        _logger.debug("[provenance] Temporary research object: %s", self.folder)

    def self_check(self) -> None:
        """Raise ValueError if this RO is closed."""
        if self.closed:
            raise ValueError(
                "This ResearchObject has already been closed and is not "
                "available for further manipulation."
            )

    def __str__(self) -> str:
        """Represent this RO as a string."""
        return f"ResearchObject <{self.ro_uuid}> in <{self.folder}>"

    def _initialize(self) -> None:
        for research_obj_folder in (
            METADATA,
            DATA,
            WORKFLOW,
            SNAPSHOT,
            PROVENANCE,
            LOGS,
        ):
            os.makedirs(os.path.join(self.folder, research_obj_folder))
        self._initialize_bagit()

    def _initialize_bagit(self) -> None:
        """Write fixed bagit header."""
        self.self_check()
        bagit = os.path.join(self.folder, "bagit.txt")
        # encoding: always UTF-8 (although ASCII would suffice here)
        with open(bagit, "w", encoding=ENCODING, newline="\n") as bag_it_file:
            # TODO: \n or \r\n ?
            bag_it_file.write("BagIt-Version: 0.97\n")
            bag_it_file.write("Tag-File-Character-Encoding: %s\n" % ENCODING)

    def open_log_file_for_activity(self, uuid_uri: str) -> Union[TextIOWrapper, WritableBagFile]:
        """Begin the per-activity log."""
        self.self_check()
        # Ensure valid UUID for safe filenames
        activity_uuid = uuid.UUID(uuid_uri)
        if activity_uuid.urn == self.engine_uuid:
            # It's the engine aka cwltool!
            name = "engine"
        else:
            name = "activity"
        p = os.path.join(LOGS, f"{name}.{activity_uuid}.txt")
        _logger.debug(f"[provenance] Opening log file for {name}: {p}")
        self.add_annotation(activity_uuid.urn, [p], CWLPROV["log"].uri)
        return self.write_bag_file(p)

    def _finalize(self) -> None:
        self._write_ro_manifest()
        self._write_bag_info()
        if not self.has_manifest:
            (Path(self.folder) / "manifest-sha1.txt").touch()

    def user_provenance(self, document: ProvDocument) -> None:
        """Add the user provenance."""
        self.self_check()
        (username, fullname) = _whoami()

        if not self.full_name:
            self.full_name = fullname

        document.add_namespace(UUID)
        document.add_namespace(ORCID)
        document.add_namespace(FOAF)
        account = document.agent(
            ACCOUNT_UUID,
            {
                provM.PROV_TYPE: FOAF["OnlineAccount"],
                "prov:label": username,
                FOAF["accountName"]: username,
            },
        )

        user = document.agent(
            self.orcid or USER_UUID,
            {
                provM.PROV_TYPE: PROV["Person"],
                "prov:label": self.full_name,
                FOAF["name"]: self.full_name,
                FOAF["account"]: account,
            },
        )
        # cwltool may be started on the shell (directly by user),
        # by shell script (indirectly by user)
        # or from a different program
        #   (which again is launched by any of the above)
        #
        # We can't tell in which way, but ultimately we're still
        # acting in behalf of that user (even if we might
        # get their name wrong!)
        document.actedOnBehalfOf(account, user)

    def write_bag_file(
        self, path: str, encoding: Optional[str] = ENCODING
    ) -> Union[TextIOWrapper, WritableBagFile]:
        """Write the bag file into our research object."""
        self.self_check()
        # For some reason below throws BlockingIOError
        # fp = BufferedWriter(WritableBagFile(self, path))
        bag_file = WritableBagFile(self, path)
        if encoding is not None:
            # encoding: match Tag-File-Character-Encoding: UTF-8
            return TextIOWrapper(cast(BinaryIO, bag_file), encoding=encoding, newline="\n")
        return bag_file

    def add_tagfile(self, path: str, timestamp: Optional[datetime.datetime] = None) -> None:
        """Add tag files to our research object."""
        self.self_check()
        checksums = {}
        # Read file to calculate its checksum
        if os.path.isdir(path):
            return
            # FIXME: do the right thing for directories
        with open(path, "rb") as tag_file:
            # FIXME: Should have more efficient open_tagfile() that
            # does all checksums in one go while writing through,
            # adding checksums after closing.
            # Below probably OK for now as metadata files
            # are not too large..?

            checksums[SHA1] = checksum_copy(tag_file, hasher=hashlib.sha1)

            tag_file.seek(0)
            checksums[SHA256] = checksum_copy(tag_file, hasher=hashlib.sha256)

            tag_file.seek(0)
            checksums[SHA512] = checksum_copy(tag_file, hasher=hashlib.sha512)

        rel_path = posix_path(os.path.relpath(path, self.folder))
        self.tagfiles.add(rel_path)
        self.add_to_manifest(rel_path, checksums)
        if timestamp is not None:
            self._file_provenance[rel_path] = {
                "createdOn": timestamp.isoformat(),
                "uri": None,
                "bundledAs": None,
                "mediatype": None,
                "conformsTo": None,
            }

    def _ro_aggregates(self) -> List[Aggregate]:
        """Gather dictionary of files to be added to the manifest."""

        def guess_mediatype(
            rel_path: str,
        ) -> Tuple[Optional[str], Optional[Union[str, List[str]]]]:
            """Return the mediatypes."""
            media_types: Dict[str, str] = {
                # Adapted from
                # https://w3id.org/bundle/2014-11-05/#media-types
                "txt": TEXT_PLAIN,
                "ttl": 'text/turtle; charset="UTF-8"',
                "rdf": "application/rdf+xml",
                "json": "application/json",
                "jsonld": "application/ld+json",
                "xml": "application/xml",
                ##
                "cwl": 'text/x+yaml; charset="UTF-8"',
                "provn": 'text/provenance-notation; charset="UTF-8"',
                "nt": "application/n-triples",
            }
            conforms_to: Dict[str, str] = {
                "provn": "http://www.w3.org/TR/2013/REC-prov-n-20130430/",
                "cwl": "https://w3id.org/cwl/",
            }

            prov_conforms_to: Dict[str, str] = {
                "provn": "http://www.w3.org/TR/2013/REC-prov-n-20130430/",
                "rdf": "http://www.w3.org/TR/2013/REC-prov-o-20130430/",
                "ttl": "http://www.w3.org/TR/2013/REC-prov-o-20130430/",
                "nt": "http://www.w3.org/TR/2013/REC-prov-o-20130430/",
                "jsonld": "http://www.w3.org/TR/2013/REC-prov-o-20130430/",
                "xml": "http://www.w3.org/TR/2013/NOTE-prov-xml-20130430/",
                "json": "http://www.w3.org/Submission/2013/SUBM-prov-json-20130424/",
            }

            extension: Optional[str] = rel_path.rsplit(".", 1)[-1].lower()
            if extension == rel_path:
                # No ".", no extension
                extension = None

            mediatype = None  # type: Optional[str]
            conformsTo = None  # type: Optional[Union[str, List[str]]]
            if extension in media_types:
                mediatype = media_types[extension]

            if extension in conforms_to:
                # TODO: Open CWL file to read its declared "cwlVersion", e.g.
                # cwlVersion = "v1.0"
                conformsTo = conforms_to[extension]

            if rel_path.startswith(posix_path(PROVENANCE)) and extension in prov_conforms_to:
                if ".cwlprov" in rel_path:
                    # Our own!
                    conformsTo = [
                        prov_conforms_to[extension],
                        CWLPROV_VERSION,
                    ]
                else:
                    # Some other PROV
                    # TODO: Recognize ProvOne etc.
                    conformsTo = prov_conforms_to[extension]
            return (mediatype, conformsTo)

        aggregates = []  # type: List[Aggregate]
        for path in self.bagged_size.keys():
            temp_path = PurePosixPath(path)
            folder = temp_path.parent
            filename = temp_path.name

            # NOTE: Here we end up aggregating the abstract
            # data items by their sha1 hash, so that it matches
            # the entity() in the prov files.

            # TODO: Change to nih:sha-256; hashes
            #  https://tools.ietf.org/html/rfc6920#section-7
            aggregate_dict = {
                "uri": "urn:hash::sha1:" + filename,
                "bundledAs": {
                    # The arcp URI is suitable ORE proxy; local to this Research Object.
                    # (as long as we don't also aggregate it by relative path!)
                    "uri": self.base_uri + path,
                    # relate it to the data/ path
                    "folder": "/%s/" % folder,
                    "filename": filename,
                },
            }  # type: Aggregate
            if path in self._file_provenance:
                # Made by workflow run, merge captured provenance
                bundledAs = aggregate_dict["bundledAs"]
                if bundledAs:
                    bundledAs.update(self._file_provenance[path])
                else:
                    aggregate_dict["bundledAs"] = cast(
                        Optional[Dict[str, Any]], self._file_provenance[path]
                    )
            else:
                # Probably made outside wf run, part of job object?
                pass
            if path in self._content_types:
                aggregate_dict["mediatype"] = self._content_types[path]

            aggregates.append(aggregate_dict)

        for path in self.tagfiles:
            if not (
                path.startswith(METADATA) or path.startswith(WORKFLOW) or path.startswith(SNAPSHOT)
            ):
                # probably a bagit file
                continue
            if path == str(PurePosixPath(METADATA) / "manifest.json"):
                # Should not really be there yet! But anyway, we won't
                # aggregate it.
                continue

            # These are local paths like metadata/provenance - but
            # we need to relativize them for our current directory for
            # as we are saved in metadata/manifest.json
            mediatype, conformsTo = guess_mediatype(path)
            rel_aggregates = {
                "uri": str(Path(os.pardir) / path),
                "mediatype": mediatype,
                "conformsTo": conformsTo,
            }  # type: Aggregate

            if path in self._file_provenance:
                # Propagate file provenance (e.g. timestamp)
                rel_aggregates.update(self._file_provenance[path])
            elif not path.startswith(SNAPSHOT):
                # make new timestamp?
                (
                    rel_aggregates["createdOn"],
                    rel_aggregates["createdBy"],
                ) = self._self_made()
            aggregates.append(rel_aggregates)
        aggregates.extend(self._external_aggregates)
        return aggregates

    def add_uri(self, uri: str, timestamp: Optional[datetime.datetime] = None) -> Aggregate:
        """Create and store an aggreate for the given URI."""
        self.self_check()
        aggr = {"uri": uri}  # type: Aggregate
        aggr["createdOn"], aggr["createdBy"] = self._self_made(timestamp=timestamp)
        self._external_aggregates.append(aggr)
        return aggr

    def add_annotation(
        self, about: str, content: List[str], motivated_by: str = "oa:describing"
    ) -> str:
        """Cheap URI relativize for current directory and /."""
        self.self_check()
        curr = self.base_uri + METADATA + "/"
        content = [c.replace(curr, "").replace(self.base_uri, "../") for c in content]
        uri = uuid.uuid4().urn
        ann = {
            "uri": uri,
            "about": about,
            "content": content,
            "oa:motivatedBy": {"@id": motivated_by},
        }  # type: Annotation
        self.annotations.append(ann)
        return uri

    def _ro_annotations(self) -> List[Annotation]:
        annotations = []  # type: List[Annotation]
        annotations.append(
            {
                "uri": uuid.uuid4().urn,
                "about": self.ro_uuid.urn,
                "content": "/",
                # https://www.w3.org/TR/annotation-vocab/#named-individuals
                "oa:motivatedBy": {"@id": "oa:describing"},
            }
        )

        # How was it run?
        # FIXME: Only primary*
        prov_files = [
            str(PurePosixPath(p).relative_to(METADATA))
            for p in self.tagfiles
            if p.startswith(posix_path(PROVENANCE)) and "/primary." in p
        ]
        annotations.append(
            {
                "uri": uuid.uuid4().urn,
                "about": self.ro_uuid.urn,
                "content": prov_files,
                # Modulation of https://www.w3.org/TR/prov-aq/
                "oa:motivatedBy": {"@id": "http://www.w3.org/ns/prov#has_provenance"},
            }
        )

        # Where is the main workflow?
        annotations.append(
            {
                "uri": uuid.uuid4().urn,
                "about": str(PurePosixPath("..") / WORKFLOW / "packed.cwl"),
                "content": None,
                "oa:motivatedBy": {"@id": "oa:highlighting"},
            }
        )

        annotations.append(
            {
                "uri": uuid.uuid4().urn,
                "about": self.ro_uuid.urn,
                "content": [
                    str(PurePosixPath("..") / WORKFLOW / "packed.cwl"),
                    str(PurePosixPath("..") / WORKFLOW / "primary-job.json"),
                ],
                "oa:motivatedBy": {"@id": "oa:linking"},
            }
        )
        # Add user-added annotations at end
        annotations.extend(self.annotations)
        return annotations

    def _authored_by(self) -> Optional[AuthoredBy]:
        authored_by = {}  # type: AuthoredBy
        if self.orcid:
            authored_by["orcid"] = self.orcid
        if self.full_name:
            authored_by["name"] = self.full_name
            if not self.orcid:
                authored_by["uri"] = USER_UUID

        if authored_by:
            return authored_by
        return None

    def _write_ro_manifest(self) -> None:
        # Does not have to be this order, but it's nice to be consistent
        filename = "manifest.json"
        createdOn, createdBy = self._self_made()
        manifest = OrderedDict(
            {
                "@context": [
                    {"@base": f"{self.base_uri}{posix_path(METADATA)}/"},
                    "https://w3id.org/bundle/context",
                ],
                "id": "/",
                "conformsTo": CWLPROV_VERSION,
                "manifest": filename,
                "createdOn": createdOn,
                "createdBy": createdBy,
                "authoredBy": self._authored_by(),
                "aggregates": self._ro_aggregates(),
                "annotations": self._ro_annotations(),
            }
        )

        json_manifest = json_dumps(manifest, indent=4, ensure_ascii=False)
        rel_path = str(PurePosixPath(METADATA) / filename)
        json_manifest += "\n"
        with self.write_bag_file(rel_path) as manifest_file:
            manifest_file.write(json_manifest)

    def _write_bag_info(self) -> None:
        with self.write_bag_file("bag-info.txt") as info_file:
            info_file.write("Bag-Software-Agent: %s\n" % self.cwltool_version)
            # FIXME: require sha-512 of payload to comply with profile?
            # FIXME: Update profile
            info_file.write("BagIt-Profile-Identifier: https://w3id.org/ro/bagit/profile\n")
            info_file.write("Bagging-Date: %s\n" % datetime.date.today().isoformat())
            info_file.write("External-Description: Research Object of CWL workflow run\n")
            if self.full_name:
                info_file.write("Contact-Name: %s\n" % self.full_name)

            # NOTE: We can't use the urn:uuid:{UUID} of the workflow run (a prov:Activity)
            # as identifier for the RO/bagit (a prov:Entity). However the arcp base URI is good.
            info_file.write("External-Identifier: %s\n" % self.base_uri)

            # Calculate size of data/ (assuming no external fetch.txt files)
            total_size = sum(self.bagged_size.values())
            num_files = len(self.bagged_size)
            info_file.write("Payload-Oxum: %d.%d\n" % (total_size, num_files))
        _logger.debug("[provenance] Generated bagit metadata: %s", self.folder)

    def generate_snapshot(self, prov_dep: CWLObjectType) -> None:
        """Copy all of the CWL files to the snapshot/ directory."""
        self.self_check()
        for key, value in prov_dep.items():
            if key == "location" and cast(str, value).split("/")[-1]:
                location = cast(str, value)
                filename = location.split("/")[-1]
                path = os.path.join(self.folder, SNAPSHOT, filename)
                filepath = ""
                if "file://" in location:
                    filepath = location[7:]
                else:
                    filepath = location

                # FIXME: What if destination path already exists?
                if os.path.exists(filepath):
                    try:
                        if os.path.isdir(filepath):
                            shutil.copytree(filepath, path)
                        else:
                            shutil.copy(filepath, path)
                        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                        self.add_tagfile(path, timestamp)
                    except PermissionError:
                        pass  # FIXME: avoids duplicate snapshotting; need better solution
            elif key in ("secondaryFiles", "listing"):
                for files in cast(MutableSequence[CWLObjectType], value):
                    if isinstance(files, MutableMapping):
                        self.generate_snapshot(files)
            else:
                pass

    def packed_workflow(self, packed: str) -> None:
        """Pack CWL description to generate re-runnable CWL object in RO."""
        self.self_check()
        rel_path = str(PurePosixPath(WORKFLOW) / "packed.cwl")
        # Write as binary
        with self.write_bag_file(rel_path, encoding=None) as write_pack:
            write_pack.write(packed)
        _logger.debug("[provenance] Added packed workflow: %s", rel_path)

    def has_data_file(self, sha1hash: str) -> bool:
        """Confirm the presence of the given file in the RO."""
        folder = os.path.join(self.folder, DATA, sha1hash[0:2])
        hash_path = os.path.join(folder, sha1hash)
        return os.path.isfile(hash_path)

    def add_data_file(
        self,
        from_fp: IO[Any],
        timestamp: Optional[datetime.datetime] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Copy inputs to data/ folder."""
        self.self_check()
        tmp_dir, tmp_prefix = os.path.split(self.temp_prefix)
        with tempfile.NamedTemporaryFile(prefix=tmp_prefix, dir=tmp_dir, delete=False) as tmp:
            checksum = checksum_copy(from_fp, tmp)

        # Calculate hash-based file path
        folder = os.path.join(self.folder, DATA, checksum[0:2])
        path = os.path.join(folder, checksum)
        # os.rename assumed safe, as our temp file should
        # be in same file system as our temp folder
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.rename(tmp.name, path)

        # Relative posix path
        rel_path = posix_path(os.path.relpath(path, self.folder))

        # Register in bagit checksum
        if Hasher == hashlib.sha1:
            self._add_to_bagit(rel_path, sha1=checksum)
        else:
            _logger.warning("[provenance] Unknown hash method %s for bagit manifest", Hasher)
            # Inefficient, bagit support need to checksum again
            self._add_to_bagit(rel_path)
        _logger.debug("[provenance] Added data file %s", path)
        if timestamp is not None:
            createdOn, createdBy = self._self_made(timestamp)
            self._file_provenance[rel_path] = cast(
                Aggregate, {"createdOn": createdOn, "createdBy": createdBy}
            )
        _logger.debug("[provenance] Relative path for data file %s", rel_path)

        if content_type is not None:
            self._content_types[rel_path] = content_type
        return rel_path

    def _self_made(
        self, timestamp: Optional[datetime.datetime] = None
    ) -> Tuple[str, Dict[str, str]]:  # createdOn, createdBy
        if timestamp is None:
            timestamp = datetime.datetime.now()
        return (
            timestamp.isoformat(),
            {"uri": self.engine_uuid, "name": self.cwltool_version},
        )

    def add_to_manifest(self, rel_path: str, checksums: Dict[str, str]) -> None:
        """Add files to the research object manifest."""
        self.self_check()
        if PurePosixPath(rel_path).is_absolute():
            raise ValueError("rel_path must be relative: %s" % rel_path)

        if os.path.commonprefix(["data/", rel_path]) == "data/":
            # payload file, go to manifest
            manifest = "manifest"
            self.has_manifest = True
        else:
            # metadata file, go to tag manifest
            manifest = "tagmanifest"

        # Add checksums to corresponding manifest files
        for method, hash_value in checksums.items():
            # File not in manifest because we bailed out on
            # existence in bagged_size above
            manifestpath = os.path.join(self.folder, f"{manifest}-{method.lower()}.txt")
            # encoding: match Tag-File-Character-Encoding: UTF-8
            with open(manifestpath, "a", encoding=ENCODING, newline="\n") as checksum_file:
                line = f"{hash_value}  {rel_path}\n"
                _logger.debug("[provenance] Added to %s: %s", manifestpath, line)
                checksum_file.write(line)

    def _add_to_bagit(self, rel_path: str, **checksums: str) -> None:
        if PurePosixPath(rel_path).is_absolute():
            raise ValueError("rel_path must be relative: %s" % rel_path)
        lpath = os.path.join(self.folder, local_path(rel_path))
        if not os.path.exists(lpath):
            raise OSError(f"File {rel_path} does not exist within RO: {lpath}")

        if rel_path in self.bagged_size:
            # Already added, assume checksum OK
            return
        self.bagged_size[rel_path] = os.path.getsize(lpath)

        if SHA1 not in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(lpath, "rb") as file_path:
                # FIXME: Need sha-256 / sha-512 as well for Research Object BagIt profile?
                checksums[SHA1] = checksum_copy(file_path, hasher=hashlib.sha1)

        self.add_to_manifest(rel_path, checksums)

    def create_job(self, builder_job: CWLObjectType, is_output: bool = False) -> CWLObjectType:
        # TODO customise the file
        """Generate the new job object with RO specific relative paths."""
        copied = copy.deepcopy(builder_job)
        relativised_input_objecttemp = {}  # type: CWLObjectType
        self._relativise_files(copied)

        def jdefault(o: Any) -> Dict[Any, Any]:
            return dict(o)

        if is_output:
            rel_path = PurePosixPath(WORKFLOW) / "primary-output.json"
        else:
            rel_path = PurePosixPath(WORKFLOW) / "primary-job.json"
        j = json_dumps(copied, indent=4, ensure_ascii=False, default=jdefault)
        with self.write_bag_file(str(rel_path)) as file_path:
            file_path.write(j + "\n")
        _logger.debug("[provenance] Generated customised job file: %s", rel_path)
        # Generate dictionary with keys as workflow level input IDs and values
        # as
        # 1) for files the relativised location containing hash
        # 2) for other attributes, the actual value.
        for key, value in copied.items():
            if isinstance(value, MutableMapping):
                if value.get("class") in ("File", "Directory"):
                    relativised_input_objecttemp[key] = value
            else:
                relativised_input_objecttemp[key] = value
        self.relativised_input_object.update(
            {k: v for k, v in relativised_input_objecttemp.items() if v}
        )
        return self.relativised_input_object

    def _relativise_files(
        self,
        structure: Union[CWLObjectType, CWLOutputType, MutableSequence[CWLObjectType]],
    ) -> None:
        """Save any file objects into the RO and update the local paths."""
        # Base case - we found a File we need to update
        _logger.debug("[provenance] Relativising: %s", structure)

        if isinstance(structure, MutableMapping):
            if structure.get("class") == "File":
                relative_path = None  # type: Optional[Union[str, PurePosixPath]]
                if "checksum" in structure:
                    raw_checksum = cast(str, structure["checksum"])
                    alg, checksum = raw_checksum.split("$")
                    if alg != SHA1:
                        raise TypeError(
                            "Only SHA1 CWL checksums are currently supported: "
                            "{}".format(structure)
                        )
                    if self.has_data_file(checksum):
                        prefix = checksum[0:2]
                        relative_path = PurePosixPath("data") / prefix / checksum

                if not (relative_path is not None and "location" in structure):
                    # Register in RO; but why was this not picked
                    # up by used_artefacts?
                    _logger.info("[provenance] Adding to RO %s", structure["location"])
                    with self.fsaccess.open(cast(str, structure["location"]), "rb") as fp:
                        relative_path = self.add_data_file(fp)
                        checksum = PurePosixPath(relative_path).name
                        structure["checksum"] = f"{SHA1}${checksum}"
                # RO-relative path as new location
                structure["location"] = str(PurePosixPath("..") / relative_path)
                if "path" in structure:
                    del structure["path"]

            if structure.get("class") == "Directory":
                # TODO: Generate anonymoys Directory with a "listing"
                # pointing to the hashed files
                del structure["location"]

            for val in structure.values():
                try:
                    self._relativise_files(cast(CWLOutputType, val))
                except OSError:
                    pass
            return

        if isinstance(structure, MutableSequence):
            for obj in structure:
                # Recurse and rewrite any nested File objects
                self._relativise_files(cast(CWLOutputType, obj))

    def close(self, save_to: Optional[str] = None) -> None:
        """Close the Research Object, optionally saving to specified folder.

        Closing will remove any temporary files used by this research object.
        After calling this method, this ResearchObject instance can no longer
        be used, except for no-op calls to .close().

        The 'saveTo' folder should not exist - if it does, it will be deleted.

        It is safe to call this function multiple times without the
        'saveTo' argument, e.g. within a try..finally block to
        ensure the temporary files of this Research Object are removed.
        """
        if save_to is None:
            if not self.closed:
                _logger.debug("[provenance] Deleting temporary %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            save_to = os.path.abspath(save_to)
            _logger.info("[provenance] Finalizing Research Object")
            self._finalize()  # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(save_to):
                _logger.info("[provenance] Deleting existing %s", save_to)
                shutil.rmtree(save_to)
            shutil.move(self.folder, save_to)
            _logger.info("[provenance] Research Object saved to %s", save_to)
            self.folder = save_to
        self.closed = True


def checksum_copy(
    src_file: IO[Any],
    dst_file: Optional[IO[Any]] = None,
    hasher: Callable[[], "hashlib._Hash"] = Hasher,
    buffersize: int = 1024 * 1024,
) -> str:
    """Compute checksums while copying a file."""
    # TODO: Use hashlib.new(Hasher_str) instead?
    checksum = hasher()
    contents = src_file.read(buffersize)
    if dst_file and hasattr(dst_file, "name") and hasattr(src_file, "name"):
        temp_location = os.path.join(os.path.dirname(dst_file.name), str(uuid.uuid4()))
        try:
            os.rename(dst_file.name, temp_location)
            os.link(src_file.name, dst_file.name)
            dst_file = None
            os.unlink(temp_location)
        except OSError:
            pass
        if os.path.exists(temp_location):
            os.rename(temp_location, dst_file.name)  # type: ignore
    while contents != b"":
        if dst_file is not None:
            dst_file.write(contents)
        checksum.update(contents)
        contents = src_file.read(buffersize)
    if dst_file is not None:
        dst_file.flush()
    return checksum.hexdigest().lower()
