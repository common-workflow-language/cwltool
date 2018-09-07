"""Stores Research Object including provenance."""
from __future__ import absolute_import

import copy
import datetime
import hashlib
import logging
import os
import os.path
import posixpath
import re
import shutil
import tempfile
import uuid
from collections import OrderedDict
from getpass import getuser
from io import BytesIO, FileIO, TextIOWrapper, open
from socket import getfqdn
from typing import (IO, Any, Callable, Dict, List, Generator, MutableMapping,
                    Optional, Set, Tuple, Union, cast)

import prov.model as provM
import six
from prov.identifier import Identifier, Namespace
from prov.model import (PROV, ProvActivity,  # pylint: disable=unused-import
                        ProvDocument, ProvEntity)
from ruamel import yaml
from schema_salad.sourceline import SourceLine
from six.moves import urllib
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text)
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .context import RuntimeContext  # pylint: disable=unused-import
from .errors import WorkflowException
from .loghandler import _logger
from .pathmapper import get_listing
from .process import Process, shortname  # pylint: disable=unused-import
from .stdfsaccess import StdFsAccess  # pylint: disable=unused-import
from .utils import json_dumps, versionstring

# Disabled due to excessive transitive dependencies
# from networkx.drawing.nx_agraph import graphviz_layout
# from networkx.drawing.nx_pydot import write_dot


GET_PW_NAM = False
try:
    # pwd is only available on Unix
    from pwd import struct_passwd  # pylint: disable=unused-import
    from pwd import getpwnam  # pylint: disable=unused-import
    GET_PW_NAME = True
except ImportError:
    pass

if TYPE_CHECKING:
    from .command_line_tool import CommandLineTool, ExpressionTool  # pylint: disable=unused-import
    from .workflow import Workflow  # pylint: disable=unused-import

if six.PY2:
    class PermissionError(OSError):  # pylint: disable=redefined-builtin
        """Needed for Python2."""

        pass
__citation__ = "https://doi.org/10.5281/zenodo.1208477"

# NOTE: Semantic versioning of the CWLProv Research Object
# **and** the cwlprov files
#
# Rough guide (major.minor.patch):
# 1. Bump major number if removing/"breaking" resources or PROV statements
# 2. Bump minor number if adding resources or PROV statements
# 3. Bump patch number for non-breaking non-adding changes,
#    e.g. fixing broken relative paths
CWLPROV_VERSION = "https://w3id.org/cwl/prov/0.5.0"

# Research Object folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")
WFDESC = Namespace("wfdesc", 'http://purl.org/wf4ever/wfdesc#')
WFPROV = Namespace("wfprov", 'http://purl.org/wf4ever/wfprov#')
WF4EVER = Namespace("wf4ever", 'http://purl.org/wf4ever/wf4ever#')
RO = Namespace("ro", 'http://purl.org/wf4ever/ro#')
ORE = Namespace("ore", 'http://www.openarchives.org/ore/terms/')
FOAF = Namespace("foaf", 'http://xmlns.com/foaf/0.1/')
SCHEMA = Namespace("schema", 'http://schema.org/')
CWLPROV = Namespace('cwlprov', 'https://w3id.org/cwl/prov#')
ORCID = Namespace("orcid", "https://orcid.org/")
UUID = Namespace("id", "urn:uuid:")

# BagIt and YAML always use UTF-8
ENCODING = "UTF-8"
TEXT_PLAIN = 'text/plain; charset="%s"' % ENCODING

# sha1, compatible with the File type's "checksum" field
# e.g. "checksum" = "sha1$47a013e660d408619d894b20806b1d5086aab03b"
# See ./cwltool/schemas/v1.0/Process.yml
Hasher = hashlib.sha1
SHA1 = "sha1"
SHA256 = "sha256"
SHA512 = "sha512"

# TODO: Better identifiers for user, at least
# these should be preserved in ~/.config/cwl for every execution
# on this host
USER_UUID = uuid.uuid4().urn
ACCOUNT_UUID = uuid.uuid4().urn


def _convert_path(path, from_path=os.path, to_path=posixpath):
    # type: (Text, Any, Any) -> Text
    if from_path == to_path:
        return path
    if from_path.isabs(path):
        raise ValueError("path must be relative: %s" % path)
        # ..as it might include system paths like "C:\" or /tmp

    split = path.split(from_path.sep)

    converted = to_path.sep.join(split)
    return converted


def _posix_path(local_path):
    # type: (Text) -> Text
    return _convert_path(local_path, os.path, posixpath)


def _local_path(posix_path):
    # type: (Text) -> Text
    return _convert_path(posix_path, posixpath, os.path)


def _whoami():
    # type: () -> Tuple[str,str]
    """Return the current operating system account as (username, fullname)."""
    username = getuser()
    fullname = username
    if GET_PW_NAM:
        pwnam = getpwnam(username)
        if pwnam:
            fullname = pwnam.pw_gecos.split(",", 1)[0]
    return (username, fullname)


class WritableBagFile(FileIO):
    """Writes files in research object."""

    def __init__(self, research_object, rel_path):
        # type: (ResearchObject, Text) -> None
        """Initialize an ROBagIt."""
        self.research_object = research_object
        if posixpath.isabs(rel_path):
            raise ValueError("rel_path must be relative: %s" % rel_path)
        self.rel_path = rel_path
        self.hashes = {SHA1: hashlib.sha1(),
                       SHA256: hashlib.sha256(),
                       SHA512: hashlib.sha512()}
        # Open file in Research Object folder
        if research_object.folder:
            path = os.path.abspath(os.path.join(research_object.folder, _local_path(rel_path)))
        if not research_object.folder or not \
                path.startswith(os.path.abspath(research_object.folder)):
            raise ValueError("Path is outside Research Object: %s" % path)
        super(WritableBagFile, self).__init__(path, mode="w")  # type: ignore

    def write(self, b):
        # type: (bytes) -> int
        total = 0
        length = len(b)
        while total < length:
            ret = super(WritableBagFile, self).write(b)
            if ret:
                total += ret
        for _ in self.hashes.values():
            _.update(b)
        return total

    def close(self):
        # FIXME: Convert below block to a ResearchObject method?
        if self.rel_path.startswith("data/"):
            self.research_object.bagged_size[self.rel_path] = self.tell()
        else:
            self.research_object.tagfiles.add(self.rel_path)

        super(WritableBagFile, self).close()
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
    def seekable(self):
        return False

    def readable(self):
        return False

    def truncate(self, size=None):
        # type: (Optional[int]) -> int
        # FIXME: This breaks contract IOBase,
        # as it means we would have to recalculate the hash
        if size is not None:
            raise IOError("WritableBagFile can't truncate")
        return self.tell()


def _check_mod_11_2(numeric_string):
    # type: (Text) -> bool
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
        total = (total+digit)*2
    remainder = total % 11
    result = (12-remainder) % 11
    if result == 10:
        checkdigit = "X"
    else:
        checkdigit = str(result)
    # Compare against last digit or X
    return nums[-1].upper() == checkdigit


def _valid_orcid(orcid):  # type: (Optional[Text]) -> Optional[Text]
    """
    Ensure orcid is a valid ORCID identifier.

    If the string is None or empty, None is returned.
    Otherwise the string must be equivalent to one of these forms:

    0000-0002-1825-0097
    orcid.org/0000-0002-1825-0097
    http://orcid.org/0000-0002-1825-0097
    https://orcid.org/0000-0002-1825-0097

    If the ORCID number or prefix is invalid, a ValueError is raised.

    The returned ORCID string is always in the form of:
    https://orcid.org/0000-0002-1825-0097
    """
    if not orcid:
        # Unspecified is OK. Empty string equivalent to unspecified
        return None
    # Liberal in what we consume, e.g. ORCID.org/0000-0002-1825-009x
    orcid = orcid.lower()
    match = re.match(
        # Note: concatinated r"" r"" below so we can add comments to pattern

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
        orcid)

    help_url = u"https://support.orcid.org/knowledgebase/articles/"\
               "116780-structure-of-the-orcid-identifier"
    if not match:
        raise ValueError(u"Invalid ORCID: %s\n%s" % (orcid, help_url))

    # Conservative in what we produce:
    # a) Ensure any checksum digit is uppercase
    orcid_num = match.group("orcid").upper()
    # b) ..and correct
    if not _check_mod_11_2(orcid_num):
        raise ValueError(
            u"Invalid ORCID checksum: %s\n%s" % (orcid_num, help_url))

    # c) Re-add the official prefix https://orcid.org/
    return u"https://orcid.org/%s" % orcid_num


class CreateProvProfile():
    """
    Provenance profile.

    Populated as the workflow runs.
    """

    def __init__(self,
                 research_object,        # type: ResearchObject
                 full_name=None,         # type: str
                 orcid=None,             # type: str
                 host_provenance=False,  # type: bool
                 user_provenance=False,  # type: bool
                 run_uuid=None,          # type: uuid.UUID
                ):  # type: (...) -> None

        self.orcid = orcid
        self.research_object = research_object
        self.folder = self.research_object.folder
        self.document = ProvDocument()
        self.host_provenance = host_provenance
        self.user_provenance = user_provenance
        self.engine_uuid = research_object.engine_uuid
        self.add_to_manifest = self.research_object.add_to_manifest
        if self.orcid:
            _logger.debug(u"[provenance] Creator ORCID: %s", self.orcid)
        self.full_name = full_name or None
        if self.full_name:
            _logger.debug(u"[provenance] Creator Full name: %s",
                          self.full_name)
        if not run_uuid:
            run_uuid = uuid.uuid4()
        self.workflow_run_uuid = run_uuid
        self.workflow_run_uri = run_uuid.urn
        self.generate_prov_doc()

    def __str__(self):
        return "CreateProvProfile <%s> in <%s>" % (
            self.workflow_run_uri, self.research_object)

    def generate_prov_doc(self):
        # type: () -> Tuple[str, ProvDocument]
        """Add basic namespaces."""
        def host_provenance(document):
            # type: (ProvDocument) -> None
            """Record host provenance."""
            document.add_namespace(CWLPROV)
            document.add_namespace(UUID)
            document.add_namespace(FOAF)

            hostname = getfqdn()
            # won't have a foaf:accountServiceHomepage for unix hosts, but
            # we can at least provide hostname
            document.agent(
                ACCOUNT_UUID, {provM.PROV_TYPE: FOAF["OnlineAccount"],
                               "prov:location": hostname,
                               CWLPROV["hostname"]: hostname})

        self.cwltool_version = "cwltool %s" % versionstring().split()[-1]
        self.document.add_namespace(
            'wfprov', 'http://purl.org/wf4ever/wfprov#')
        # document.add_namespace('prov', 'http://www.w3.org/ns/prov#')
        self.document.add_namespace(
            'wfdesc', 'http://purl.org/wf4ever/wfdesc#')
        # TODO: Make this ontology. For now only has cwlprov:image
        self.document.add_namespace('cwlprov', 'https://w3id.org/cwl/prov#')
        self.document.add_namespace('foaf', 'http://xmlns.com/foaf/0.1/')
        self.document.add_namespace('schema', 'http://schema.org/')
        self.document.add_namespace('orcid', 'https://orcid.org/')
        self.document.add_namespace('id', 'urn:uuid:')
        # NOTE: Internet draft expired 2004-03-04 (!)
        #  https://tools.ietf.org/html/draft-thiemann-hash-urn-01
        # TODO: Change to nih:sha-256; hashes
        #  https://tools.ietf.org/html/rfc6920#section-7
        self.document.add_namespace('data', 'urn:hash::sha1:')
        # Also needed for docker images
        self.document.add_namespace(SHA256, "nih:sha-256;")

        # info only, won't really be used by prov as sub-resources use /
        self.document.add_namespace(
            'researchobject', self.research_object.base_uri)
        # annotations
        self.metadata_ns = self.document.add_namespace(
            'metadata', self.research_object.base_uri + _posix_path(METADATA)
            + "/")
        # Pre-register provenance directory so we can refer to its files
        self.provenance_ns = self.document.add_namespace(
            'provenance', self.research_object.base_uri
            + _posix_path(PROVENANCE) + "/")
        ro_identifier_workflow = self.research_object.base_uri \
            + "workflow/packed.cwl#"
        self.wf_ns = self.document.add_namespace("wf", ro_identifier_workflow)
        ro_identifier_input = self.research_object.base_uri \
            + "workflow/primary-job.json#"
        self.document.add_namespace("input", ro_identifier_input)

        # More info about the account (e.g. username, fullname)
        # may or may not have been previously logged by user_provenance()
        # .. but we always know cwltool was launched (directly or indirectly)
        # by a user account, as cwltool is a command line tool
        account = self.document.agent(ACCOUNT_UUID)
        if self.orcid or self.full_name:
            person = {provM.PROV_TYPE: PROV["Person"],
                      "prov:type": SCHEMA["Person"]}
            if self.full_name:
                person["prov:label"] = self.full_name
                person["foaf:name"] = self.full_name
                person["schema:name"] = self.full_name
            else:
                # TODO: Look up name from ORCID API?
                pass
            agent = self.document.agent(self.orcid or uuid.uuid4().urn,
                                        person)
            self.document.actedOnBehalfOf(account, agent)
        else:
            if self.host_provenance:
                host_provenance(self.document)
            if self.user_provenance:
                self.research_object.user_provenance(self.document)
        # The execution of cwltool
        wfengine = self.document.agent(
            self.engine_uuid,
            {provM.PROV_TYPE: PROV["SoftwareAgent"],
             "prov:type": WFPROV["WorkflowEngine"],
             "prov:label": self.cwltool_version})
        # FIXME: This datetime will be a bit too delayed, we should
        # capture when cwltool.py earliest started?
        self.document.wasStartedBy(
            wfengine, None, account, datetime.datetime.now())
        # define workflow run level activity
        self.document.activity(
            self.workflow_run_uri, datetime.datetime.now(), None,
            {provM.PROV_TYPE: WFPROV["WorkflowRun"],
             "prov:label": "Run of workflow/packed.cwl#main"})
            # association between SoftwareAgent and WorkflowRun
        main_workflow = "wf:main"
        self.document.wasAssociatedWith(
            self.workflow_run_uri, self.engine_uuid, main_workflow)
        self.document.wasStartedBy(
            self.workflow_run_uri, None, self.engine_uuid,
            datetime.datetime.now())
        return (self.workflow_run_uri, self.document)

    def evaluate(self,
                 process,           # type: Process
                 job,               # type: Any
                 job_order_object,  # type: Dict[Text, Text]
                 make_fs_access,    # type: Callable[[Text], StdFsAccess]
                 research_obj       # type: ResearchObject
                ):  # type: (...) -> Optional[str]
        """Evaluate the nature of job and initialize the activity start."""
        process_run_id = None
        research_obj.make_fs_access = make_fs_access
        if not hasattr(process, "steps"):
            # record provenance of an independent commandline tool execution
            self.prospective_prov(job)
            customised_job = copy_job_order(job, job_order_object)
            self.used_artefacts(customised_job, self.workflow_run_uri)
            research_obj.create_job(customised_job, job)
            # self.used_artefacts(inputs, self.workflow_run_uri)
            name = ""
            if hasattr(job, "name"):
                name = str(job.name)
            process_name = urllib.parse.quote(name, safe=":/,#")
            process_run_id = self.workflow_run_uri
        elif hasattr(job, "workflow"):
            # record provenance for the workflow execution
            self.prospective_prov(job)
            customised_job = copy_job_order(job, job_order_object)
            self.used_artefacts(customised_job, self.workflow_run_uri)
            # inputs = research_obj.create_job(customised_job)
            # self.used_artefacts(inputs, self.workflow_run_uri)
        else:  # in case of commandline tool execution as part of workflow
            name = ""
            if hasattr(job, "name"):
                name = str(job.name)
            process_name = urllib.parse.quote(name, safe=":/,#")
            process_run_id = self.start_process(process_name)
        return process_run_id

    def start_process(self, process_name, process_run_id=None):
        # type: (Any, str, str) -> str
        """Record the start of each Process."""
        if process_run_id is None:
            process_run_id = uuid.uuid4().urn
        if self.workflow_run_uri:
            prov_label = "Run of workflow/packed.cwl#main/"+process_name
            self.document.activity(
                process_run_id, None, None,
                {provM.PROV_TYPE: WFPROV["ProcessRun"],
                 provM.PROV_LABEL: prov_label})
            self.document.wasAssociatedWith(
                process_run_id, self.engine_uuid, str("wf:main/" + process_name))
            self.document.wasStartedBy(
                process_run_id, None, self.workflow_run_uri,
                datetime.datetime.now(), None, None)
        else:
            prov_label = "Run of CommandLineTool/packed.cwl#main/"
            self.document.activity(
                process_run_id, None, None,
                {provM.PROV_TYPE: WFPROV["ProcessRun"],
                 provM.PROV_LABEL: prov_label})
            self.document.wasAssociatedWith(
                process_run_id, self.engine_uuid, str("wf:main/"+process_name))
            self.document.wasStartedBy(
                process_run_id, None, self.engine_uuid, datetime.datetime.now(),
                None, None)
        return process_run_id

    def declare_file(self, value):
        # type: (MutableMapping) -> Tuple[ProvEntity,ProvEntity,str]
        if value["class"] != "File":
            raise ValueError("Must have class:File: %s" % value)
        # Need to determine file hash aka RO filename
        entity = None # type: Optional[ProvEntity]
        checksum = None
        if 'checksum' in value:
            csum = value['checksum']
            (method, checksum) = csum.split("$", 1)
            assert checksum
            if method == SHA1 and \
                self.research_object.has_data_file(checksum):
                entity = self.document.entity("data:" + checksum)

        if not entity and 'location' in value:
            location = str(value['location'])
            # If we made it here, we'll have to add it to the RO
            assert self.research_object.make_fs_access
            fsaccess = self.research_object.make_fs_access("")
            with fsaccess.open(location, "rb") as fhandle:
                relative_path = self.research_object.add_data_file(fhandle)
                # FIXME: This naively relies on add_data_file setting hash as filename
                checksum = posixpath.basename(relative_path)
                entity = self.document.entity(
                    "data:" + checksum, {provM.PROV_TYPE: WFPROV["Artifact"]})
                if "checksum" not in value:
                    value["checksum"] = "%s$%s" % (SHA1, checksum)


        if not entity and 'contents' in value:
            # Anonymous file, add content as string
            entity, checksum = self.declare_string(value["contents"])

        # By here one of them should have worked!
        if not entity:
            raise ValueError("class:File but missing checksum/location/content: %r" % value)


        # Track filename and extension, this is generally useful only for
        # secondaryFiles. Note that multiple uses of a file might thus record
        # different names for the same entity, so we'll
        # make/track a specialized entity by UUID
        file_id = value.setdefault("@id", uuid.uuid4().urn)
        # A specialized entity that has just these names
        file_entity = self.document.entity(
            file_id, [(provM.PROV_TYPE, WFPROV["Artifact"]),
                      (provM.PROV_TYPE, WF4EVER["File"])])  # type: ProvEntity

        if "basename" in value:
            file_entity.add_attributes({CWLPROV["basename"]: value["basename"]})
        if "nameroot" in value:
            file_entity.add_attributes({CWLPROV["nameroot"]: value["nameroot"]})
        if "nameext" in value:
            file_entity.add_attributes({CWLPROV["nameext"]: value["nameext"]})
        self.document.specializationOf(file_entity, entity)

        # Check for secondaries
        for sec in value.get("secondaryFiles", ()):
            # TODO: Record these in a specializationOf entity with UUID?
            (sec_entity, _, _) = self.declare_file(sec)
            # We don't know how/when/where the secondary file was generated,
            # but CWL convention is a kind of summary/index derived
            # from the original file. As its generally in a different format
            # then prov:Quotation is not appropriate.
            self.document.derivation(
                sec_entity, file_entity,
                other_attributes={PROV["type"]: CWLPROV["SecondaryFile"]})

        assert entity
        assert checksum
        return file_entity, entity, checksum

    def declare_directory(self, value):  # type: (MutableMapping) -> ProvEntity
        """Register any nested files/directories."""
        # FIXME: Calculate a hash-like identifier for directory
        # so we get same value if it's the same filenames/hashes
        # in a different location.
        # For now, mint a new UUID to identify this directory, but
        # attempt to keep it inside the value dictionary
        dir_id = value.setdefault("@id", uuid.uuid4().urn)

        # New annotation file to keep the ORE Folder listing
        ore_doc_fn = dir_id.replace("urn:uuid:", "directory-") + ".ttl"
        dir_bundle = self.document.bundle(self.metadata_ns[ore_doc_fn])

        coll = self.document.entity(
            dir_id, [(provM.PROV_TYPE, WFPROV["Artifact"]),
                     (provM.PROV_TYPE, PROV["Collection"]),
                     (provM.PROV_TYPE, PROV["Dictionary"]),
                     (provM.PROV_TYPE, RO["Folder"])])
        # ORE description of ro:Folder, saved separately
        coll_b = dir_bundle.entity(
            dir_id, [(provM.PROV_TYPE, RO["Folder"]),
                     (provM.PROV_TYPE, ORE["Aggregation"])])
        self.document.mentionOf(dir_id + "#ore", dir_id, dir_bundle.identifier)

        # dir_manifest = dir_bundle.entity(
        #     dir_bundle.identifier, {PROV["type"]: ORE["ResourceMap"],
        #                             ORE["describes"]: coll_b.identifier})

        coll_attribs = [(ORE["isDescribedBy"], dir_bundle.identifier)]
        coll_b_attribs = []  # type: List[Tuple[Identifier, ProvEntity]]

        # FIXME: .listing might not be populated yet - hopefully
        # a later call to this method will sort that
        is_empty = True

        if not "listing" in value:
            assert self.research_object.make_fs_access
            fsaccess = self.research_object.make_fs_access("")
            get_listing(fsaccess, value)
        for entry in value.get("listing", []):
            is_empty = False
            # Declare child-artifacts
            entity = self.declare_artefact(entry)
            self.document.membership(coll, entity)
            # Membership relation aka our ORE Proxy
            m_id = uuid.uuid4().urn
            m_entity = self.document.entity(m_id)
            m_b = dir_bundle.entity(m_id)

            # PROV-O style Dictionary
            # https://www.w3.org/TR/prov-dictionary/#dictionary-ontological-definition
            # ..as prov.py do not currently allow PROV-N extensions
            # like hadDictionaryMember(..)
            m_entity.add_asserted_type(PROV["KeyEntityPair"])

            m_entity.add_attributes({
                PROV["pairKey"]: entry["basename"],
                PROV["pairEntity"]: entity,
            })

            # As well as a being a
            # http://wf4ever.github.io/ro/2016-01-28/ro/#FolderEntry
            m_b.add_asserted_type(RO["FolderEntry"])
            m_b.add_asserted_type(ORE["Proxy"])
            m_b.add_attributes({
                RO["entryName"]: entry["basename"],
                ORE["proxyIn"]: coll,
                ORE["proxyFor"]: entity,

            })
            coll_attribs.append((PROV["hadDictionaryMember"], m_entity))
            coll_b_attribs.append((ORE["aggregates"], m_b))

        coll.add_attributes(coll_attribs)
        coll_b.add_attributes(coll_b_attribs)

        # Also Save ORE Folder as annotation metadata
        ore_doc = ProvDocument()
        ore_doc.add_namespace(ORE)
        ore_doc.add_namespace(RO)
        ore_doc.add_namespace(UUID)
        ore_doc.add_bundle(dir_bundle)
        ore_doc = ore_doc.flattened()
        ore_doc_path = posixpath.join(_posix_path(METADATA), ore_doc_fn)
        with self.research_object.write_bag_file(ore_doc_path) as provenance_file:
            ore_doc.serialize(provenance_file, format="rdf", rdf_format="turtle")
        self.research_object.add_annotation(dir_id, [ore_doc_fn], ORE["isDescribedBy"].uri)

        if is_empty:
            # Empty directory
            coll.add_asserted_type(PROV["EmptyCollection"])
            coll.add_asserted_type(PROV["EmptyDictionary"])
        self.research_object.add_uri(coll.identifier.uri)
        return coll

    def declare_string(self, value):
        # type: (Union[Text, str]) -> Tuple[ProvEntity,Text]
        """Save as string in UTF-8."""
        byte_s = BytesIO(str(value).encode(ENCODING))
        data_file = self.research_object.add_data_file(byte_s, content_type=TEXT_PLAIN)
        checksum = posixpath.basename(data_file)
        # FIXME: Don't naively assume add_data_file uses hash in filename!
        data_id = "data:%s" % posixpath.split(data_file)[1]
        entity = self.document.entity(
            data_id, {provM.PROV_TYPE: WFPROV["Artifact"],
                      provM.PROV_VALUE: str(value)})  # type: ProvEntity
        return entity, checksum

    def declare_artefact(self, value):
        # type: (Any) -> ProvEntity
        """Create data artefact entities for all file objects."""
        if value is None:
            # FIXME: If this can happen in CWL, we'll
            # need a better way to represent this in PROV
            return self.document.entity(
                CWLPROV["None"], {provM.PROV_LABEL: "None"})

        if isinstance(value, (bool, int, float)):
            # Typically used in job documents for flags

            # FIXME: Make consistent hash URIs for these
            # that somehow include the type
            # (so "1" != 1 != "1.0" != true)
            entity = self.document.entity(
                uuid.uuid4().urn, {provM.PROV_VALUE: value})
            self.research_object.add_uri(entity.identifier.uri)
            return entity

        if isinstance(value, (Text, str)):
            (entity, _) = self.declare_string(value)
            return entity

        if isinstance(value, bytes):
            # If we got here then we must be in Python 3
            byte_s = BytesIO(value)
            data_file = self.research_object.add_data_file(byte_s)
            # FIXME: Don't naively assume add_data_file uses hash in filename!
            data_id = "data:%s" % posixpath.split(data_file)[1]
            return self.document.entity(
                data_id, {provM.PROV_TYPE: WFPROV["Artifact"],
                          provM.PROV_VALUE: str(value)})

        if isinstance(value, MutableMapping):
            if "@id" in value:
                # Already processed this value, but it might not be in this PROV
                entities = self.document.get_record(value["@id"])
                if entities:
                    return entities[0]
                # else, unknown in PROV, re-add below as if it's fresh

            # Base case - we found a File we need to update
            if value.get("class") == "File":
                (entity, _, _) = self.declare_file(value)
                value["@id"] = entity.identifier.uri
                return entity

            if value.get("class") == "Directory":
                entity = self.declare_directory(value)
                value["@id"] = entity.identifier.uri
                return entity
            coll_id = value.setdefault("@id", uuid.uuid4().urn)
            # some other kind of dictionary?
            # TODO: also Save as JSON
            coll = self.document.entity(
                coll_id, [(provM.PROV_TYPE, WFPROV["Artifact"]),
                          (provM.PROV_TYPE, PROV["Collection"]),
                          (provM.PROV_TYPE, PROV["Dictionary"])])

            if value.get("class"):
                _logger.warning("Unknown data class %s.", value["class"])
                # FIXME: The class might be "http://example.com/somethingelse"
                coll.add_asserted_type(CWLPROV[value["class"]])

            # Let's iterate and recurse
            coll_attribs = []  # type: List[Tuple[Identifier, ProvEntity]]
            for (key, val) in value.items():
                v_ent = self.declare_artefact(val)
                self.document.membership(coll, v_ent)
                m_entity = self.document.entity(uuid.uuid4().urn)
                # Note: only support PROV-O style dictionary
                # https://www.w3.org/TR/prov-dictionary/#dictionary-ontological-definition
                # as prov.py do not easily allow PROV-N extensions
                m_entity.add_asserted_type(PROV["KeyEntityPair"])
                m_entity.add_attributes({
                    PROV["pairKey"]: str(key),
                    PROV["pairEntity"]: v_ent
                })
                coll_attribs.append((PROV["hadDictionaryMember"], m_entity))
            coll.add_attributes(coll_attribs)
            self.research_object.add_uri(coll.identifier.uri)
            return coll

        # some other kind of Collection?
        # TODO: also save as JSON
        try:
            members = []
            for each_input_obj in iter(value):
                # Recurse and register any nested objects
                e = self.declare_artefact(each_input_obj)
                members.append(e)

            # If we reached this, then we were allowed to iterate
            coll = self.document.entity(
                uuid.uuid4().urn, [(provM.PROV_TYPE, WFPROV["Artifact"]),
                                   (provM.PROV_TYPE, PROV["Collection"])])
            if not members:
                coll.add_asserted_type(PROV["EmptyCollection"])
            else:
                for member in members:
                    # FIXME: This won't preserve order, for that
                    # we would need to use PROV.Dictionary
                    # with numeric keys
                    self.document.membership(coll, member)
            self.research_object.add_uri(coll.identifier.uri)
            # FIXME: list value does not support adding "@id"
            return coll
        except TypeError:
            _logger.warning("Unrecognized type %s of %r",
                            type(value), value)
            # Let's just fall back to Python repr()
            entity = self.document.entity(
                uuid.uuid4().urn, {provM.PROV_LABEL: repr(value)})
            self.research_object.add_uri(entity.identifier.uri)
            return entity

    def used_artefacts(self,
                       job_order,            # type: Dict
                       process_run_id,       # type: str
                       name=None             # type: str
                      ):  # type: (...) -> None
        """Add used() for each data artefact."""
        # FIXME: Use workflow name in packed.cwl, "main" is wrong for nested workflows
        base = "main"
        if name:
            base += "/" + name
        for key, value in job_order.items():
            prov_role = self.wf_ns["%s/%s" % (base, key)]
            entity = self.declare_artefact(value)
            self.document.used(
                process_run_id, entity, datetime.datetime.now(), None,
                {"prov:role": prov_role})

    def generate_output_prov(self,
                             final_output,    # type: Dict[Text, Any]
                             process_run_id,  # type: Optional[str]
                             name             # type: Optional[Text]
                            ):   # type: (...) -> None
        """Call wasGeneratedBy() for each output,copy the files into the RO."""
        # Record "when" as early as possible
        when = datetime.datetime.now()

        # For each output, find/register the corresponding
        # entity (UUID) and document it as generated in
        # a role corresponding to the output
        for output, value in final_output.items():
            entity = self.declare_artefact(value)
            if name:
                name = urllib.parse.quote(str(name), safe=":/,#")
                # FIXME: Probably not "main" in nested workflows
                role = self.wf_ns["main/%s/%s" % (name, output)]
            else:
                role = self.wf_ns["main/%s" % output]

            if not process_run_id:
                process_run_id = self.workflow_run_uri

            self.document.wasGeneratedBy(
                entity, process_run_id, when, None, {"prov:role": role})

    def prospective_prov(self, job):
        # type: (Any) -> None
        """Create prospective prov recording as wfdesc prov:Plan."""
        if not hasattr(job, "steps"):
            # direct command line tool execution
            self.document.entity(
                "wf:main", {provM.PROV_TYPE: WFDESC["Process"],
                            "prov:type": PROV["Plan"],
                            "prov:label":"Prospective provenance"})
            return

        self.document.entity(
            "wf:main", {provM.PROV_TYPE: WFDESC["Workflow"],
                        "prov:type": PROV["Plan"],
                        "prov:label":"Prospective provenance"})

        steps = []
        for step in job.steps:
            stepnametemp = "wf:main/"+str(step.name)[5:]
            stepname = urllib.parse.quote(stepnametemp, safe=":/,#")
            steps.append(stepname)
            step = self.document.entity(
                stepname, {provM.PROV_TYPE: WFDESC["Process"],
                           "prov:type": PROV["Plan"]})
            self.document.entity(
                "wf:main", {"wfdesc:hasSubProcess": step,
                            "prov:label": "Prospective provenance"})
        # TODO: Declare roles/parameters as well

    def activity_has_provenance(self, activity, prov_ids):
        # type: (str, List[Identifier]) -> None
        """Add http://www.w3.org/TR/prov-aq/ relations to nested PROV files."""
        # NOTE: The below will only work if the corresponding metadata/provenance arcp URI
        # is a pre-registered namespace in the PROV Document
        attribs = [(PROV["has_provenance"], prov_id) for prov_id in prov_ids]
        self.document.activity(activity, other_attributes=attribs)
        # Tip: we can't use https://www.w3.org/TR/prov-links/#term-mention
        # as prov:mentionOf() is only for entities, not activities
        uris = [i.uri for i in prov_ids]
        self.research_object.add_annotation(activity, uris, PROV["has_provenance"].uri)

    def finalize_prov_profile(self, name):
        # type: (Optional[Text]) -> List[Identifier]
        """Transfer the provenance related files to the RO."""
        # NOTE: Relative posix path
        if name is None:
            # master workflow, fixed filenames
            filename = "primary.cwlprov"
        else:
            # ASCII-friendly filename, avoiding % as we don't want %2520 in manifest.json
            wf_name = urllib.parse.quote(str(name), safe="").replace("%", "_")
            # Note that the above could cause overlaps for similarly named
            # workflows, but that's OK as we'll also include run uuid
            # which also covers thhe case of this step being run in
            # multiple places or iterations
            filename = "%s.%s.cwlprov" % (wf_name, self.workflow_run_uuid)

        basename = posixpath.join(_posix_path(PROVENANCE), filename)

        # TODO: Also support other profiles than CWLProv, e.g. ProvOne

        # list of prov identifiers of provenance files
        prov_ids = []

        # https://www.w3.org/TR/prov-xml/
        with self.research_object.write_bag_file(basename + ".xml") as provenance_file:
            self.document.serialize(provenance_file, format="xml", indent=4)
            prov_ids.append(self.provenance_ns[filename + ".xml"])

        # https://www.w3.org/TR/prov-n/
        with self.research_object.write_bag_file(basename + ".provn") as provenance_file:
            self.document.serialize(provenance_file, format="provn", indent=2)
            prov_ids.append(self.provenance_ns[filename + ".provn"])

        # https://www.w3.org/Submission/prov-json/
        with self.research_object.write_bag_file(basename + ".json") as provenance_file:
            self.document.serialize(provenance_file, format="json", indent=2)
            prov_ids.append(self.provenance_ns[filename + ".json"])

        # "rdf" aka https://www.w3.org/TR/prov-o/
        # which can be serialized to ttl/nt/jsonld (and more!)

        # https://www.w3.org/TR/turtle/
        with self.research_object.write_bag_file(basename + ".ttl") as provenance_file:
            self.document.serialize(provenance_file, format="rdf", rdf_format="turtle")
            prov_ids.append(self.provenance_ns[filename + ".ttl"])

        # https://www.w3.org/TR/n-triples/
        with self.research_object.write_bag_file(basename + ".nt") as provenance_file:
            self.document.serialize(provenance_file, format="rdf", rdf_format="ntriples")
            prov_ids.append(self.provenance_ns[filename + ".nt"])

        # https://www.w3.org/TR/json-ld/
        # TODO: Use a nice JSON-LD context
        # see also https://eprints.soton.ac.uk/395985/
        # 404 Not Found on https://provenance.ecs.soton.ac.uk/prov.jsonld :(
        with self.research_object.write_bag_file(basename + ".jsonld") as provenance_file:
            self.document.serialize(provenance_file, format="rdf", rdf_format="json-ld")
            prov_ids.append(self.provenance_ns[filename + ".jsonld"])

        _logger.debug("[provenance] added provenance: %s", prov_ids)
        return prov_ids


class ResearchObject():
    """CWLProv Research Object."""

    def __init__(self, temp_prefix_ro="tmp", orcid=None, full_name=None):
        # type: (str, Text, str) -> None

        self.temp_prefix = temp_prefix_ro
        self.orcid = _valid_orcid(orcid)
        self.full_name = full_name or None
        self.folder = os.path.abspath(tempfile.mkdtemp(prefix=temp_prefix_ro))  # type: Optional[Text]
        # map of filename "data/de/alsdklkas": 12398123 bytes
        self.bagged_size = {}  # type: Dict
        self.tagfiles = set()  # type: Set
        self._file_provenance = {}  # type: Dict
        self._external_aggregates = [] # type: List[Dict]
        self.annotations = [] # type: List[Dict]
        self._content_types = {} # type: Dict[Text,str]

        # These should be replaced by generate_prov_doc when workflow/run IDs are known:
        self.engine_uuid = "urn:uuid:%s" % uuid.uuid4()
        self.ro_uuid = uuid.uuid4()
        self.base_uri = "arcp://uuid,%s/" % self.ro_uuid
        self.cwltool_version = "cwltool (unknown version)"
        ##
        # This function will be added by create_job()
        self.make_fs_access = None  # type: Optional[Callable[[Text], StdFsAccess]]
        self.relativised_input_object = {}  # type: Dict[Any, Any]

        self._initialize()
        _logger.debug(u"[provenance] Temporary research object: %s",
                      self.folder)

    def __str__(self):
        return "ResearchObject <%s> in <%s>" % (
            self.ro_uuid, self.folder)

    def _initialize(self):
        # type: (...) -> None
        assert self.folder
        for research_obj_folder in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, research_obj_folder))
        self._initialize_bagit()

    def _initialize_bagit(self):
        # type: (...) -> None
        # Write fixed bagit header
        assert self.folder
        bagit = os.path.join(self.folder, "bagit.txt")
        # encoding: always UTF-8 (although ASCII would suffice here)
        # newline: ensure LF also on Windows
        with open(bagit, "w", encoding=ENCODING, newline='\n') as bag_it_file:
            # TODO: \n or \r\n ?
            bag_it_file.write(u"BagIt-Version: 0.97\n")
            bag_it_file.write(u"Tag-File-Character-Encoding: %s\n" % ENCODING)

    def _finalize(self):
        # type: () -> None
        self._write_ro_manifest()
        self._write_bag_info()


    def user_provenance(self, document):
        # type: (ProvDocument) -> None
        """Add the user provenance."""
        (username, fullname) = _whoami()

        if not self.full_name:
            self.full_name = fullname

        document.add_namespace(UUID)
        document.add_namespace(ORCID)
        document.add_namespace(FOAF)
        account = document.agent(
            ACCOUNT_UUID, {provM.PROV_TYPE: FOAF["OnlineAccount"],
                           "prov:label": username,
                           FOAF["accountName"]: username})

        user = document.agent(
            self.orcid or USER_UUID, {provM.PROV_TYPE: PROV["Person"],
                                      "prov:label": self.full_name,
                                      FOAF["name"]: self.full_name,
                                      FOAF["account"]: account})
        # cwltool may be started on the shell (directly by user),
        # by shell script (indirectly by user)
        # or from a different program
        #   (which again is launched by any of the above)
        #
        # We can't tell in which way, but ultimately we're still
        # acting in behalf of that user (even if we might
        # get their name wrong!)
        document.actedOnBehalfOf(account, user)

    def write_bag_file(self, path, encoding=ENCODING):
        # type: (Text, Optional[str]) -> IO
        """Write the bag file into our research object."""
        # For some reason below throws BlockingIOError
        #fp = BufferedWriter(WritableBagFile(self, path))
        bag_file = cast(IO, WritableBagFile(self, path))
        if encoding:
            # encoding: match Tag-File-Character-Encoding: UTF-8
            # newline: ensure LF also on Windows
            return cast(IO,
                        TextIOWrapper(bag_file, encoding=encoding, newline="\n"))
        return bag_file

    def add_tagfile(self, path, when=None):
        # type: (Text, datetime.datetime) -> None
        """Add tag files to our research object."""
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
            # Older Python's might not have all checksums
            if hashlib.sha256:
                tag_file.seek(0)
                checksums[SHA256] = checksum_copy(tag_file, hasher=hashlib.sha256)
            if hashlib.sha512:
                tag_file.seek(0)
                checksums[SHA512] = checksum_copy(tag_file, hasher=hashlib.sha512)
        assert self.folder
        rel_path = _posix_path(os.path.relpath(path, self.folder))
        self.tagfiles.add(rel_path)
        self.add_to_manifest(rel_path, checksums)
        if when:
            self._file_provenance[rel_path] = {"createdOn": when.isoformat()}

    def _ro_aggregates(self):
        # type: () -> List[Dict[str,Any]]
        """Gather dictionary of files to be added to the manifest."""
        def guess_mediatype(rel_path):
            # type: (str) -> Dict[str,str]
            """Return the mediatypes."""
            media_types = {
                # Adapted from
                # https://w3id.org/bundle/2014-11-05/#media-types

                "txt": TEXT_PLAIN,
                "ttl": 'text/turtle; charset="UTF-8"',
                "rdf": 'application/rdf+xml',
                "json": 'application/json',
                "jsonld": 'application/ld+json',
                "xml": 'application/xml',
                ##
                "cwl": 'text/x+yaml; charset="UTF-8"',
                "provn": 'text/provenance-notation; charset="UTF-8"',
                "nt": 'application/n-triples',
            }
            conforms_to = {
                "provn": 'http://www.w3.org/TR/2013/REC-prov-n-20130430/',
                "cwl": 'https://w3id.org/cwl/',
            }

            prov_conforms_to = {
                "provn": 'http://www.w3.org/TR/2013/REC-prov-n-20130430/',
                "rdf": 'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
                "ttl": 'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
                "nt": 'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
                "jsonld": 'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
                "xml": 'http://www.w3.org/TR/2013/NOTE-prov-xml-20130430/',
                "json": 'http://www.w3.org/Submission/2013/SUBM-prov-json-20130424/',
            }


            extension = rel_path.rsplit(".", 1)[-1].lower()  # type: Optional[str]
            if extension == rel_path:
                # No ".", no extension
                extension = None

            local_aggregate = {}  # type: Dict[str, Any]
            if extension in media_types:
                local_aggregate["mediatype"] = media_types[extension]

            if extension in conforms_to:
                # TODO: Open CWL file to read its declared "cwlVersion", e.g.
                # cwlVersion = "v1.0"
                local_aggregate["conformsTo"] = conforms_to[extension]

            if (rel_path.startswith(_posix_path(PROVENANCE))
                    and extension in prov_conforms_to):
                if ".cwlprov" in rel_path:
                    # Our own!
                    local_aggregate["conformsTo"] = [prov_conforms_to[extension], CWLPROV_VERSION]
                else:
                    # Some other PROV
                    # TODO: Recognize ProvOne etc.
                    local_aggregate["conformsTo"] = prov_conforms_to[extension]
            return local_aggregate

        aggregates = [] # type: List[Dict]
        for path in self.bagged_size.keys():
            aggregate_dict = {}  # type: Dict[str,Any]

            (folder, filename) = posixpath.split(path)

            # NOTE: Here we end up aggregating the abstract
            # data items by their sha1 hash, so that it matches
            # the entity() in the prov files.

            # TODO: Change to nih:sha-256; hashes
            #  https://tools.ietf.org/html/rfc6920#section-7
            aggregate_dict["uri"] = 'urn:hash::sha1:' + filename
            aggregate_dict["bundledAs"] = {
                # The arcp URI is suitable ORE proxy; local to this Research Object.
                # (as long as we don't also aggregate it by relative path!)
                "uri": self.base_uri + path,
                # relate it to the data/ path
                "folder": "/%s/" % folder,
                "filename": filename,
            }
            if path in self._file_provenance:
                # Made by workflow run, merge captured provenance
                aggregate_dict["bundledAs"].update(self._file_provenance[path])
            else:
                # Probably made outside wf run, part of job object?
                pass
            if path in self._content_types:
                aggregate_dict["mediatype"] = self._content_types[path]

            aggregates.append(aggregate_dict)

        for path in self.tagfiles:
            if (not (path.startswith(METADATA) or path.startswith(WORKFLOW) or
                     path.startswith(SNAPSHOT))):
                # probably a bagit file
                continue
            if path == posixpath.join(METADATA, "manifest.json"):
                # Should not really be there yet! But anyway, we won't
                # aggregate it.
                continue

            rel_aggregates = {} # type: Dict[str,Any]
            # These are local paths like metadata/provenance - but
            # we need to relativize them for our current directory for
            # as we are saved in metadata/manifest.json
            uri = posixpath.relpath(path, METADATA)

            rel_aggregates["uri"] = uri
            rel_aggregates.update(guess_mediatype(path))

            if path in self._file_provenance:
                # Propagate file provenance (e.g. timestamp)
                rel_aggregates.update(self._file_provenance[path])
            elif not path.startswith(SNAPSHOT):
                # make new timestamp?
                rel_aggregates.update(self._self_made())
            aggregates.append(rel_aggregates)
        aggregates.extend(self._external_aggregates)
        return aggregates

    def add_uri(self, uri, when=None):
        # type: (str, Optional[datetime.datetime]) -> Dict
        aggr = self._self_made(when=when)
        aggr["uri"] = uri
        self._external_aggregates.append(aggr)
        return aggr

    def add_annotation(self, about, content, motivated_by="oa:describing"):
        # type: (str, List[str], str) -> str
        """Cheap URI relativize for current directory and /."""
        curr = self.base_uri + METADATA + "/"
        content = [c.replace(curr, "").replace(self.base_uri, "../")
                   for c in content]
        uri = uuid.uuid4().urn
        ann = {
            "uri": uri,
            "about": about,
            "content": content,
            "oa:motivatedBy": {"@id": motivated_by}
        }
        self.annotations.append(ann)
        return uri

    def _ro_annotations(self):
        # type: () -> List[Dict]
        annotations = []
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.ro_uuid.urn,
            "content": "/",
            # https://www.w3.org/TR/annotation-vocab/#named-individuals
            "oa:motivatedBy": {"@id": "oa:describing"}
        })

        # How was it run?
        # FIXME: Only primary*
        prov_files = [posixpath.relpath(p, METADATA) for p in self.tagfiles
                      if p.startswith(_posix_path(PROVENANCE))
                      and "/primary." in p]
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.ro_uuid.urn,
            "content": prov_files,
            # Modulation of https://www.w3.org/TR/prov-aq/
            "oa:motivatedBy": {"@id": "http://www.w3.org/ns/prov#has_provenance"}
        })

        # Where is the main workflow?
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": posixpath.join("..", WORKFLOW, "packed.cwl"),
            "oa:motivatedBy": {"@id": "oa:highlighting"}
        })

        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.ro_uuid.urn,
            "content": [posixpath.join("..", WORKFLOW, "packed.cwl"),
                        posixpath.join("..", WORKFLOW, "primary-job.json")],
            "oa:motivatedBy": {"@id": "oa:linking"}
        })
        # Add user-added annotations at end
        annotations.extend(self.annotations)
        return annotations

    def _authored_by(self):
        # type: () -> Dict
        authored_by = {}
        if self.orcid:
            authored_by["orcid"] = self.orcid
        if self.full_name:
            authored_by["name"] = self.full_name
            if not self.orcid:
                authored_by["uri"] = USER_UUID

        if authored_by:
            return {"authoredBy": authored_by}
        return {}


    def _write_ro_manifest(self):
        # type: () -> None

        # Does not have to be this order, but it's nice to be consistent
        manifest = OrderedDict()  # type: Dict[str,Any]
        manifest["@context"] = [
            {"@base": "%s%s/" % (self.base_uri, _posix_path(METADATA))},
            "https://w3id.org/bundle/context"
        ]
        manifest["id"] = "/"
        manifest["conformsTo"] = CWLPROV_VERSION
        filename = "manifest.json"
        manifest["manifest"] = filename
        manifest.update(self._self_made())
        manifest.update(self._authored_by())
        manifest["aggregates"] = self._ro_aggregates()
        manifest["annotations"] = self._ro_annotations()

        json_manifest = json_dumps(manifest, indent=4, ensure_ascii=False)
        rel_path = posixpath.join(_posix_path(METADATA), filename)
        with self.write_bag_file(rel_path) as manifest_file:
            manifest_file.write(json_manifest + "\n")

    def _write_bag_info(self):
        # type: () -> None

        with self.write_bag_file("bag-info.txt") as info_file:
            info_file.write(u"Bag-Software-Agent: %s\n" % self.cwltool_version)
            # FIXME: require sha-512 of payload to comply with profile?
            # FIXME: Update profile
            info_file.write(u"BagIt-Profile-Identifier: https://w3id.org/ro/bagit/profile\n")
            info_file.write(u"Bagging-Date: %s\n" % datetime.date.today().isoformat())
            info_file.write(u"External-Description: Research Object of CWL workflow run\n")
            if self.full_name:
                info_file.write(u"Contact-Name: %s\n" % self.full_name)

            # NOTE: We can't use the urn:uuid:{UUID} of the workflow run (a prov:Activity)
            # as identifier for the RO/bagit (a prov:Entity). However the arcp base URI is good.
            info_file.write(u"External-Identifier: %s\n" % self.base_uri)

            # Calculate size of data/ (assuming no external fetch.txt files)
            total_size = sum(self.bagged_size.values())
            num_files = len(self.bagged_size)
            info_file.write(u"Payload-Oxum: %d.%d\n" % (total_size, num_files))
        _logger.debug(u"[provenance] Generated bagit metadata: %s",
                      self.folder)

    def generate_snapshot(self, prov_dep):
        # type: (MutableMapping[Text, Any]) -> None
        """Copy all of the CWL files to the snapshot/ directory."""
        assert self.folder
        for key, value in prov_dep.items():
            if key == "location" and value.split("/")[-1]:
                filename = value.split("/")[-1]
                path = os.path.join(self.folder, SNAPSHOT, filename)
                filepath = ''
                if "file://" in value:
                    filepath = value[7:]
                else:
                    filepath = value

                # FIXME: What if destination path already exists?
                if os.path.exists(filepath):
                    try:
                        if os.path.isdir(filepath):
                            shutil.copytree(filepath, path)
                        else:
                            shutil.copy(filepath, path)
                        when = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                        self.add_tagfile(path, when)
                    except PermissionError:
                        pass  # FIXME: avoids duplicate snapshotting; need better solution
            elif key in ("secondaryFiles", "listing"):
                for files in value:
                    if isinstance(files, MutableMapping):
                        self.generate_snapshot(files)
            else:
                pass

    def packed_workflow(self, packed):  # type: (Text) -> None
        """Pack CWL description to generate re-runnable CWL object in RO."""
        rel_path = posixpath.join(_posix_path(WORKFLOW), "packed.cwl")
        # Write as binary
        with self.write_bag_file(rel_path, encoding=None) as write_pack:
            # YAML is always UTF8, but json.dumps gives us str in py2
            write_pack.write(packed.encode(ENCODING))
        _logger.debug(u"[provenance] Added packed workflow: %s", rel_path)

    def has_data_file(self, sha1hash):
        # type: (str) -> bool
        assert self.folder
        folder = os.path.join(self.folder, DATA, sha1hash[0:2])
        return os.path.isfile(os.path.join(folder, sha1hash))

    def add_data_file(self, from_fp, when=None, content_type=None):
        # type: (IO, Optional[datetime.datetime], Optional[str]) -> Text
        """Copy inputs to data/ folder."""
        with tempfile.NamedTemporaryFile(
                prefix=self.temp_prefix, delete=False) as tmp:
            checksum = checksum_copy(from_fp, tmp)

        # Calculate hash-based file path
        assert self.folder
        folder = os.path.join(self.folder, DATA, checksum[0:2])
        path = os.path.join(folder, checksum)
        # os.rename assumed safe, as our temp file should
        # be in same file system as our temp folder
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.rename(tmp.name, path)

        # Relative posix path
        # (to avoid \ on Windows)
        rel_path = _posix_path(os.path.relpath(path, self.folder))

        # Register in bagit checksum
        if Hasher == hashlib.sha1:
            self._add_to_bagit(rel_path, sha1=checksum)
        else:
            _logger.warning(
                u"[provenance] Unknown hash method %s for bagit manifest",
                Hasher)
            # Inefficient, bagit support need to checksum again
            self._add_to_bagit(rel_path)
        _logger.debug(u"[provenance] Added data file %s", path)
        if when:
            self._file_provenance[rel_path] = self._self_made(when)
        _logger.debug(u"[provenance] Relative path for data file %s", rel_path)

        if content_type:
            self._content_types[rel_path] = content_type
        return rel_path

    def _self_made(self, when=None):
        # type: (Optional[datetime.datetime]) -> Dict[str,Any]
        if when is None:
            when = datetime.datetime.now()
        return {
            "createdOn": when.isoformat(),
            "createdBy": {"uri": self.engine_uuid,
                          "name": self.cwltool_version}
        }

    def add_to_manifest(self, rel_path, checksums):
        # type: (Text, Dict[str,str]) -> None
        """Add files to the research object manifest."""
        if posixpath.isabs(rel_path):
            raise ValueError("rel_path must be relative: %s" % rel_path)

        if posixpath.commonprefix(["data/", rel_path]) == "data/":
            # payload file, go to manifest
            manifest = "manifest"
        else:
            # metadata file, go to tag manifest
            manifest = "tagmanifest"

        assert self.folder
        # Add checksums to corresponding manifest files
        for (method, hash_value) in checksums.items():
            # File not in manifest because we bailed out on
            # existence in bagged_size above
            manifestpath = os.path.join(
                self.folder, "%s-%s.txt" % (manifest, method.lower()))
            # encoding: match Tag-File-Character-Encoding: UTF-8
            # newline: ensure LF also on Windows
            with open(manifestpath, "a", encoding=ENCODING, newline='\n') \
                    as checksum_file:
                line = u"%s  %s\n" % (hash_value, rel_path)
                _logger.debug(u"[provenance] Added to %s: %s", manifestpath, line)
                checksum_file.write(line)


    def _add_to_bagit(self, rel_path, **checksums):
        # type: (Text, Any) -> None
        if posixpath.isabs(rel_path):
            raise ValueError("rel_path must be relative: %s" % rel_path)
        assert self.folder
        local_path = os.path.join(self.folder, _local_path(rel_path))
        if not os.path.exists(local_path):
            raise IOError("File %s does not exist within RO: %s" % (rel_path, local_path))

        if rel_path in self.bagged_size:
            # Already added, assume checksum OK
            return
        self.bagged_size[rel_path] = os.path.getsize(local_path)

        if SHA1 not in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(local_path, "rb") as file_path:
                # FIXME: Need sha-256 / sha-512 as well for Research Object BagIt profile?
                checksums[SHA1] = checksum_copy(file_path, hasher=hashlib.sha1)

        self.add_to_manifest(rel_path, checksums)

    def create_job(self,
                   builder_job,  # type: Dict[Text, Any]
                   wf_job=None,  # type: Callable[[Dict[Text, Text], Callable[[Any, Any], Any], RuntimeContext], Generator[Any, None, None]]
                   is_output=False
                  ):  # type: (...) -> Dict
        #TODO customise the file
        """Generate the new job object with RO specific relative paths."""
        copied = copy.deepcopy(builder_job)
        relativised_input_objecttemp = {}  # type: Dict[Text, Any]
        self._relativise_files(copied)
        def jdefault(o):
            return dict(o)
        if is_output:
            rel_path = posixpath.join(_posix_path(WORKFLOW), "primary-output.json")
        else:
            rel_path = posixpath.join(_posix_path(WORKFLOW), "primary-job.json")
        j = json_dumps(copied, indent=4, ensure_ascii=False, default=jdefault)
        with self.write_bag_file(rel_path) as file_path:
            file_path.write(j + u"\n")
        _logger.debug(u"[provenance] Generated customised job file: %s",
                      rel_path)
        # Generate dictionary with keys as workflow level input IDs and values
        # as
        # 1) for files the relativised location containing hash
        # 2) for other attributes, the actual value.
        relativised_input_objecttemp = {}
        for key, value in copied.items():
            if isinstance(value, MutableMapping):
                if value.get("class") in ("File", "Directory"):
                    relativised_input_objecttemp[key] = value
            else:
                relativised_input_objecttemp[key] = value
        self.relativised_input_object.update(
            {k: v for k, v in relativised_input_objecttemp.items() if v})
        return self.relativised_input_object

    def _relativise_files(self, structure):
        # type: (Any, Dict[Any, Any]) -> None
        """Save any file objects into the RO and update the local paths."""
        # Base case - we found a File we need to update
        _logger.debug(u"[provenance] Relativising: %s", structure)

        if isinstance(structure, MutableMapping):
            if structure.get("class") == "File":
                relative_path = None
                if "checksum" in structure:
                    sha1, checksum = structure["checksum"].split("$")
                    assert sha1 == SHA1
                    if self.has_data_file(checksum):
                        prefix = checksum[0:2]
                        relative_path = posixpath.join(
                            "data", prefix, checksum)

                if not relative_path and "location" in structure:
                    # Register in RO; but why was this not picked
                    # up by used_artefacts?
                    _logger.warning("File not previously registered in RO: %s",
                                    yaml.dump(structure))
                    fsaccess = self.make_fs_access("")
                    with fsaccess.open(structure["location"], "rb") as fp:
                        relative_path = self.add_data_file(fp)
                        checksum = posixpath.basename(relative_path)
                        structure["checksum"] = "%s$%s" % (SHA1, checksum)
                if relative_path:
                    # RO-relative path as new location
                    structure["location"] = posixpath.join("..", relative_path)
                else:
                    _logger.warning("Could not determine RO path for file %s", structure)
                if "path" in structure:
                    del structure["path"]

            if structure.get("class") == "Directory":
                # TODO: Generate anonymoys Directory with a "listing"
                # pointing to the hashed files
                del structure["location"]

            for val in structure.values():
                self._relativise_files(val)
            return

        if isinstance(structure, (str, Text)):
            # Just a string value, no need to iterate further
            return
        try:
            for obj in iter(structure):
                # Recurse and rewrite any nested File objects
                self._relativise_files(obj)
        except TypeError:
            pass

    def close(self, save_to=None):
        # type: (Optional[str]) -> None
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
            if self.folder:
                _logger.debug(u"[provenance] Deleting temporary %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            save_to = os.path.abspath(save_to)
            _logger.info(u"[provenance] Finalizing Research Object")
            self._finalize()  # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(save_to):
                _logger.info(u"[provenance] Deleting existing %s", save_to)
                shutil.rmtree(save_to)
            assert self.folder
            shutil.move(self.folder, save_to)
            _logger.info(u"[provenance] Research Object saved to %s", save_to)
        # Forget our temporary folder, which should no longer exists
        # This makes later close() a no-op
        self.folder = None

def checksum_copy(file_path,            # type: IO
                  copy_to_fp=None,      # type: Optional[IO]
                  hasher=Hasher,        # type: Callable[[], Any]
                  buffersize=1024*1024  # type: int
                 ): # type: (...) -> str
    """Compute checksums while copying a file."""
    # TODO: Use hashlib.new(Hasher_str) instead?
    checksum = hasher()
    contents = file_path.read(buffersize)
    while contents != b"":
        if copy_to_fp is not None:
            copy_to_fp.write(contents)
        checksum.update(contents)
        contents = file_path.read(buffersize)
    if copy_to_fp is not None:
        copy_to_fp.flush()
    return checksum.hexdigest().lower()

def copy_job_order(job, job_order_object):
    # type: (Any,Any) -> Any
    """Create copy of job object for provenance."""
    if not hasattr(job, "tool"):
        # direct command line tool execution
        return job_order_object
    customised_job = {}  # new job object for RO
    for each, i in enumerate(job.tool["inputs"]):
        with SourceLine(job.tool["inputs"], each, WorkflowException,
                        _logger.isEnabledFor(logging.DEBUG)):
            iid = shortname(i["id"])
            if iid in job_order_object:
                customised_job[iid] = copy.deepcopy(job_order_object[iid])
                # add the input element in dictionary for provenance
            elif "default" in i:
                customised_job[iid] = copy.deepcopy(i["default"])
                # add the default elements in the dictionary for provenance
            else:
                pass
    return customised_job
