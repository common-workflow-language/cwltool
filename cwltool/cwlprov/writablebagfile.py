"""Stores class definition of ResearchObject and WritableBagFile."""

import copy
import datetime
import hashlib
import os
import shutil
import uuid
from array import array
from collections import OrderedDict
from io import FileIO, TextIOWrapper
from mmap import mmap
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict, MutableMapping, Optional, Union, cast

from schema_salad.utils import json_dumps

from ..loghandler import _logger
from ..utils import CWLObjectType, local_path, posix_path
from .provenance_constants import (
    CWLPROV,
    CWLPROV_VERSION,
    ENCODING,
    LOGS,
    METADATA,
    SHA1,
    SHA256,
    SHA512,
    WORKFLOW,
)
from .ro import ResearchObject


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
            val.update(real_b)
        return total

    def close(self) -> None:
        """
        Flush and close this stream.

        Finalize checksums and manifests.
        """
        # FIXME: Convert below block to a ResearchObject method?
        if self.rel_path.startswith("data/"):
            self.research_object.bagged_size[self.rel_path] = self.tell()
        else:
            self.research_object.tagfiles.add(self.rel_path)

        super().close()
        # { "sha1": "f572d396fae9206628714fb2ce00f72e94f2258f" }
        checksums = {}
        for name, val in self.hashes.items():
            checksums[name] = val.hexdigest().lower()
        self.research_object.add_to_manifest(self.rel_path, checksums)

    # To simplify our hash calculation we won't support
    # seeking, reading or truncating, as we can't do
    # similar seeks in the current hash.
    # TODO: Support these? At the expense of invalidating
    # the current hash, then having to recalculate at close()
    def seekable(self) -> bool:
        """Return False, seeking is not supported."""
        return False

    def readable(self) -> bool:
        """Return False, reading is not supported."""
        return False

    def truncate(self, size: Optional[int] = None) -> int:
        """Resize the stream, only if we haven't started writing."""
        # FIXME: This breaks contract IOBase,
        # as it means we would have to recalculate the hash
        if size is not None:
            raise OSError("WritableBagFile can't truncate")
        return self.tell()


def write_bag_file(
    research_object: "ResearchObject", path: str, encoding: Optional[str] = ENCODING
) -> Union[TextIOWrapper, WritableBagFile]:
    """Write the bag file into our research object."""
    research_object.self_check()
    # For some reason below throws BlockingIOError
    # fp = BufferedWriter(WritableBagFile(self, path))
    bag_file = WritableBagFile(research_object, path)
    if encoding is not None:
        # encoding: match Tag-File-Character-Encoding: UTF-8
        return TextIOWrapper(cast(BinaryIO, bag_file), encoding=encoding, newline="\n")
    return bag_file


def open_log_file_for_activity(
    research_object: "ResearchObject", uuid_uri: str
) -> Union[TextIOWrapper, WritableBagFile]:
    """Begin the per-activity log."""
    research_object.self_check()
    # Ensure valid UUID for safe filenames
    activity_uuid = uuid.UUID(uuid_uri)
    if activity_uuid.urn == research_object.engine_uuid:
        # It's the engine aka cwltool!
        name = "engine"
    else:
        name = "activity"
    p = os.path.join(LOGS, f"{name}.{activity_uuid}.txt")
    _logger.debug(f"[provenance] Opening log file for {name}: {p}")
    research_object.add_annotation(activity_uuid.urn, [p], CWLPROV["log"].uri)
    return write_bag_file(research_object, p)


def _write_ro_manifest(research_object: "ResearchObject") -> None:
    # Does not have to be this order, but it's nice to be consistent
    filename = "manifest.json"
    createdOn, createdBy = research_object._self_made()
    manifest = OrderedDict(
        {
            "@context": [
                {"@base": f"{research_object.base_uri}{posix_path(METADATA)}/"},
                "https://w3id.org/bundle/context",
            ],
            "id": "/",
            "conformsTo": CWLPROV_VERSION,
            "manifest": filename,
            "createdOn": createdOn,
            "createdBy": createdBy,
            "authoredBy": research_object._authored_by(),
            "aggregates": research_object._ro_aggregates(),
            "annotations": research_object._ro_annotations(),
        }
    )

    json_manifest = json_dumps(manifest, indent=4, ensure_ascii=False)
    rel_path = str(PurePosixPath(METADATA) / filename)
    json_manifest += "\n"
    with write_bag_file(research_object, rel_path) as manifest_file:
        manifest_file.write(json_manifest)


def _write_bag_info(research_object: "ResearchObject") -> None:
    with write_bag_file(research_object, "bag-info.txt") as info_file:
        info_file.write("Bag-Software-Agent: %s\n" % research_object.cwltool_version)
        # FIXME: require sha-512 of payload to comply with profile?
        # FIXME: Update profile
        info_file.write("BagIt-Profile-Identifier: https://w3id.org/ro/bagit/profile\n")
        info_file.write("Bagging-Date: %s\n" % datetime.date.today().isoformat())
        info_file.write("External-Description: Research Object of CWL workflow run\n")
        if research_object.full_name:
            info_file.write("Contact-Name: %s\n" % research_object.full_name)

        # NOTE: We can't use the urn:uuid:{UUID} of the workflow run (a prov:Activity)
        # as identifier for the RO/bagit (a prov:Entity). However the arcp base URI is good.
        info_file.write("External-Identifier: %s\n" % research_object.base_uri)

        # Calculate size of data/ (assuming no external fetch.txt files)
        total_size = sum(research_object.bagged_size.values())
        num_files = len(research_object.bagged_size)
        info_file.write("Payload-Oxum: %d.%d\n" % (total_size, num_files))
    _logger.debug("[provenance] Generated bagit metadata: %s", research_object.folder)


def _finalize(research_object: "ResearchObject") -> None:
    _write_ro_manifest(research_object)
    _write_bag_info(research_object)
    if not research_object.has_manifest:
        (Path(research_object.folder) / "manifest-sha1.txt").touch()


def close_ro(research_object: "ResearchObject", save_to: Optional[str] = None) -> None:
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
        if not research_object.closed:
            _logger.debug("[provenance] Deleting temporary %s", research_object.folder)
            shutil.rmtree(research_object.folder, ignore_errors=True)
    else:
        save_to = os.path.abspath(save_to)
        _logger.info("[provenance] Finalizing Research Object")
        _finalize(research_object)  # write manifest etc.
        # TODO: Write as archive (.zip or .tar) based on extension?

        if os.path.isdir(save_to):
            _logger.info("[provenance] Deleting existing %s", save_to)
            shutil.rmtree(save_to)
        shutil.move(research_object.folder, save_to)
        _logger.info("[provenance] Research Object saved to %s", save_to)
        research_object.folder = save_to
    research_object.closed = True


def packed_workflow(research_object: "ResearchObject", packed: str) -> None:
    """Pack CWL description to generate re-runnable CWL object in RO."""
    research_object.self_check()
    rel_path = str(PurePosixPath(WORKFLOW) / "packed.cwl")
    # Write as binary
    with write_bag_file(research_object, rel_path, encoding=None) as write_pack:
        write_pack.write(packed)
    _logger.debug("[provenance] Added packed workflow: %s", rel_path)


def create_job(
    research_object: "ResearchObject", builder_job: CWLObjectType, is_output: bool = False
) -> CWLObjectType:
    # TODO customise the file
    """Generate the new job object with RO specific relative paths."""
    copied = copy.deepcopy(builder_job)
    relativised_input_objecttemp: CWLObjectType = {}
    research_object._relativise_files(copied)

    def jdefault(o: Any) -> Dict[Any, Any]:
        return dict(o)

    if is_output:
        rel_path = PurePosixPath(WORKFLOW) / "primary-output.json"
    else:
        rel_path = PurePosixPath(WORKFLOW) / "primary-job.json"
    j = json_dumps(copied, indent=4, ensure_ascii=False, default=jdefault)
    with write_bag_file(research_object, str(rel_path)) as file_path:
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
    research_object.relativised_input_object.update(
        {k: v for k, v in relativised_input_objecttemp.items() if v}
    )
    return research_object.relativised_input_object
