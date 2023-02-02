import copy
import datetime
import logging
import urllib
import uuid
from io import BytesIO
from pathlib import PurePath, PurePosixPath
from socket import getfqdn
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from prov.identifier import Identifier, QualifiedName
from prov.model import PROV, PROV_LABEL, PROV_TYPE, PROV_VALUE, ProvDocument, ProvEntity
from schema_salad.sourceline import SourceLine

from .errors import WorkflowException
from .job import CommandLineJob, JobBase
from .loghandler import _logger
from .process import Process, shortname
from .provenance_constants import (
    ACCOUNT_UUID,
    CWLPROV,
    ENCODING,
    FOAF,
    METADATA,
    ORE,
    PROVENANCE,
    RO,
    SCHEMA,
    SHA1,
    SHA256,
    TEXT_PLAIN,
    UUID,
    WF4EVER,
    WFDESC,
    WFPROV,
)
from .stdfsaccess import StdFsAccess
from .utils import CWLObjectType, JobsType, get_listing, posix_path, versionstring
from .workflow_job import WorkflowJob

if TYPE_CHECKING:
    from .provenance import ResearchObject


def copy_job_order(job: Union[Process, JobsType], job_order_object: CWLObjectType) -> CWLObjectType:
    """Create copy of job object for provenance."""
    if not isinstance(job, WorkflowJob):
        # direct command line tool execution
        return job_order_object
    customised_job: CWLObjectType = {}
    # new job object for RO
    debug = _logger.isEnabledFor(logging.DEBUG)
    for each, i in enumerate(job.tool["inputs"]):
        with SourceLine(job.tool["inputs"], each, WorkflowException, debug):
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


class ProvenanceProfile:
    """
    Provenance profile.

    Populated as the workflow runs.
    """

    def __init__(
        self,
        research_object: "ResearchObject",
        full_name: str,
        host_provenance: bool,
        user_provenance: bool,
        orcid: str,
        fsaccess: StdFsAccess,
        run_uuid: Optional[uuid.UUID] = None,
    ) -> None:
        """Initialize the provenance profile."""
        self.fsaccess = fsaccess
        self.orcid = orcid
        self.research_object = research_object
        self.folder = self.research_object.folder
        self.document = ProvDocument()
        self.host_provenance = host_provenance
        self.user_provenance = user_provenance
        self.engine_uuid = research_object.engine_uuid
        self.add_to_manifest = self.research_object.add_to_manifest
        if self.orcid:
            _logger.debug("[provenance] Creator ORCID: %s", self.orcid)
        self.full_name = full_name
        if self.full_name:
            _logger.debug("[provenance] Creator Full name: %s", self.full_name)
        self.workflow_run_uuid = run_uuid or uuid.uuid4()
        self.workflow_run_uri = self.workflow_run_uuid.urn
        self.generate_prov_doc()

    def __str__(self) -> str:
        """Represent this Provenvance profile as a string."""
        return "ProvenanceProfile <{}> in <{}>".format(
            self.workflow_run_uri,
            self.research_object,
        )

    def generate_prov_doc(self) -> Tuple[str, ProvDocument]:
        """Add basic namespaces."""

        def host_provenance(document: ProvDocument) -> None:
            """Record host provenance."""
            document.add_namespace(CWLPROV)
            document.add_namespace(UUID)
            document.add_namespace(FOAF)

            hostname = getfqdn()
            # won't have a foaf:accountServiceHomepage for unix hosts, but
            # we can at least provide hostname
            document.agent(
                ACCOUNT_UUID,
                {
                    PROV_TYPE: FOAF["OnlineAccount"],
                    "prov:location": hostname,
                    CWLPROV["hostname"]: hostname,
                },
            )

        self.cwltool_version = "cwltool %s" % versionstring().split()[-1]
        self.document.add_namespace("wfprov", "http://purl.org/wf4ever/wfprov#")
        # document.add_namespace('prov', 'http://www.w3.org/ns/prov#')
        self.document.add_namespace("wfdesc", "http://purl.org/wf4ever/wfdesc#")
        # TODO: Make this ontology. For now only has cwlprov:image
        self.document.add_namespace("cwlprov", "https://w3id.org/cwl/prov#")
        self.document.add_namespace("foaf", "http://xmlns.com/foaf/0.1/")
        self.document.add_namespace("schema", "http://schema.org/")
        self.document.add_namespace("orcid", "https://orcid.org/")
        self.document.add_namespace("id", "urn:uuid:")
        # NOTE: Internet draft expired 2004-03-04 (!)
        #  https://tools.ietf.org/html/draft-thiemann-hash-urn-01
        # TODO: Change to nih:sha-256; hashes
        #  https://tools.ietf.org/html/rfc6920#section-7
        self.document.add_namespace("data", "urn:hash::sha1:")
        # Also needed for docker images
        self.document.add_namespace(SHA256, "nih:sha-256;")

        # info only, won't really be used by prov as sub-resources use /
        self.document.add_namespace("researchobject", self.research_object.base_uri)
        # annotations
        self.metadata_ns = self.document.add_namespace(
            "metadata", self.research_object.base_uri + METADATA + "/"
        )
        # Pre-register provenance directory so we can refer to its files
        self.provenance_ns = self.document.add_namespace(
            "provenance", self.research_object.base_uri + posix_path(PROVENANCE) + "/"
        )
        ro_identifier_workflow = self.research_object.base_uri + "workflow/packed.cwl#"
        self.wf_ns = self.document.add_namespace("wf", ro_identifier_workflow)
        ro_identifier_input = self.research_object.base_uri + "workflow/primary-job.json#"
        self.document.add_namespace("input", ro_identifier_input)

        # More info about the account (e.g. username, fullname)
        # may or may not have been previously logged by user_provenance()
        # .. but we always know cwltool was launched (directly or indirectly)
        # by a user account, as cwltool is a command line tool
        account = self.document.agent(ACCOUNT_UUID)
        if self.orcid or self.full_name:
            person: Dict[Union[str, Identifier], Any] = {
                PROV_TYPE: PROV["Person"],
                "prov:type": SCHEMA["Person"],
            }
            if self.full_name:
                person["prov:label"] = self.full_name
                person["foaf:name"] = self.full_name
                person["schema:name"] = self.full_name
            else:
                # TODO: Look up name from ORCID API?
                pass
            agent = self.document.agent(self.orcid or uuid.uuid4().urn, person)
            self.document.actedOnBehalfOf(account, agent)
        else:
            if self.host_provenance:
                host_provenance(self.document)
            if self.user_provenance:
                self.research_object.user_provenance(self.document)
        # The execution of cwltool
        wfengine = self.document.agent(
            self.engine_uuid,
            {
                PROV_TYPE: PROV["SoftwareAgent"],
                "prov:type": WFPROV["WorkflowEngine"],
                "prov:label": self.cwltool_version,
            },
        )
        # FIXME: This datetime will be a bit too delayed, we should
        # capture when cwltool.py earliest started?
        self.document.wasStartedBy(wfengine, None, account, datetime.datetime.now())
        # define workflow run level activity
        self.document.activity(
            self.workflow_run_uri,
            datetime.datetime.now(),
            None,
            {
                PROV_TYPE: WFPROV["WorkflowRun"],
                "prov:label": "Run of workflow/packed.cwl#main",
            },
        )
        # association between SoftwareAgent and WorkflowRun
        main_workflow = "wf:main"
        self.document.wasAssociatedWith(self.workflow_run_uri, self.engine_uuid, main_workflow)
        self.document.wasStartedBy(
            self.workflow_run_uri, None, self.engine_uuid, datetime.datetime.now()
        )
        return (self.workflow_run_uri, self.document)

    def evaluate(
        self,
        process: Process,
        job: JobsType,
        job_order_object: CWLObjectType,
        research_obj: "ResearchObject",
    ) -> None:
        """Evaluate the nature of job."""
        if not hasattr(process, "steps"):
            # record provenance of independent commandline tool executions
            self.prospective_prov(job)
            customised_job = copy_job_order(job, job_order_object)
            self.used_artefacts(customised_job, self.workflow_run_uri)
            research_obj.create_job(customised_job)
        elif hasattr(job, "workflow"):
            # record provenance of workflow executions
            self.prospective_prov(job)
            customised_job = copy_job_order(job, job_order_object)
            self.used_artefacts(customised_job, self.workflow_run_uri)

    def record_process_start(
        self, process: Process, job: JobsType, process_run_id: Optional[str] = None
    ) -> Optional[str]:
        if not hasattr(process, "steps"):
            process_run_id = self.workflow_run_uri
        elif not hasattr(job, "workflow"):
            # commandline tool execution as part of workflow
            name = ""
            if isinstance(job, (CommandLineJob, JobBase, WorkflowJob)):
                name = job.name
            process_name = urllib.parse.quote(name, safe=":/,#")
            process_run_id = self.start_process(process_name, datetime.datetime.now())
        return process_run_id

    def start_process(
        self,
        process_name: str,
        when: datetime.datetime,
        process_run_id: Optional[str] = None,
    ) -> str:
        """Record the start of each Process."""
        if process_run_id is None:
            process_run_id = uuid.uuid4().urn
        prov_label = "Run of workflow/packed.cwl#main/" + process_name
        self.document.activity(
            process_run_id,
            None,
            None,
            {PROV_TYPE: WFPROV["ProcessRun"], PROV_LABEL: prov_label},
        )
        self.document.wasAssociatedWith(
            process_run_id, self.engine_uuid, str("wf:main/" + process_name)
        )
        self.document.wasStartedBy(process_run_id, None, self.workflow_run_uri, when, None, None)
        return process_run_id

    def record_process_end(
        self,
        process_name: str,
        process_run_id: str,
        outputs: Union[CWLObjectType, MutableSequence[CWLObjectType], None],
        when: datetime.datetime,
    ) -> None:
        self.generate_output_prov(outputs, process_run_id, process_name)
        self.document.wasEndedBy(process_run_id, None, self.workflow_run_uri, when)

    def declare_file(self, value: CWLObjectType) -> Tuple[ProvEntity, ProvEntity, str]:
        if value["class"] != "File":
            raise ValueError("Must have class:File: %s" % value)
        # Need to determine file hash aka RO filename
        entity: Optional[ProvEntity] = None
        checksum = None
        if "checksum" in value:
            csum = cast(str, value["checksum"])
            (method, checksum) = csum.split("$", 1)
            if method == SHA1 and self.research_object.has_data_file(checksum):
                entity = self.document.entity("data:" + checksum)

        if not entity and "location" in value:
            location = str(value["location"])
            # If we made it here, we'll have to add it to the RO
            with self.fsaccess.open(location, "rb") as fhandle:
                relative_path = self.research_object.add_data_file(fhandle)
                # FIXME: This naively relies on add_data_file setting hash as filename
                checksum = PurePath(relative_path).name
                entity = self.document.entity("data:" + checksum, {PROV_TYPE: WFPROV["Artifact"]})
                if "checksum" not in value:
                    value["checksum"] = f"{SHA1}${checksum}"

        if not entity and "contents" in value:
            # Anonymous file, add content as string
            entity, checksum = self.declare_string(cast(str, value["contents"]))

        # By here one of them should have worked!
        if not entity or not checksum:
            raise ValueError("class:File but missing checksum/location/content: %r" % value)

        # Track filename and extension, this is generally useful only for
        # secondaryFiles. Note that multiple uses of a file might thus record
        # different names for the same entity, so we'll
        # make/track a specialized entity by UUID
        file_id = cast(str, value.setdefault("@id", uuid.uuid4().urn))
        # A specialized entity that has just these names
        file_entity = self.document.entity(
            file_id,
            [(PROV_TYPE, WFPROV["Artifact"]), (PROV_TYPE, WF4EVER["File"])],
        )

        if "basename" in value:
            file_entity.add_attributes({CWLPROV["basename"]: cast(str, value["basename"])})
        if "nameroot" in value:
            file_entity.add_attributes({CWLPROV["nameroot"]: cast(str, value["nameroot"])})
        if "nameext" in value:
            file_entity.add_attributes({CWLPROV["nameext"]: cast(str, value["nameext"])})
        self.document.specializationOf(file_entity, entity)

        # Check for secondaries
        for sec in cast(MutableSequence[CWLObjectType], value.get("secondaryFiles", [])):
            # TODO: Record these in a specializationOf entity with UUID?
            if sec["class"] == "File":
                (sec_entity, _, _) = self.declare_file(sec)
            elif sec["class"] == "Directory":
                sec_entity = self.declare_directory(sec)
            else:
                raise ValueError(f"Got unexpected secondaryFiles value: {sec}")
            # We don't know how/when/where the secondary file was generated,
            # but CWL convention is a kind of summary/index derived
            # from the original file. As its generally in a different format
            # then prov:Quotation is not appropriate.
            self.document.derivation(
                sec_entity,
                file_entity,
                other_attributes={PROV["type"]: CWLPROV["SecondaryFile"]},
            )

        return file_entity, entity, checksum

    def declare_directory(self, value: CWLObjectType) -> ProvEntity:
        """Register any nested files/directories."""
        # FIXME: Calculate a hash-like identifier for directory
        # so we get same value if it's the same filenames/hashes
        # in a different location.
        # For now, mint a new UUID to identify this directory, but
        # attempt to keep it inside the value dictionary
        dir_id = cast(str, value.setdefault("@id", uuid.uuid4().urn))

        # New annotation file to keep the ORE Folder listing
        ore_doc_fn = dir_id.replace("urn:uuid:", "directory-") + ".ttl"
        dir_bundle = self.document.bundle(self.metadata_ns[ore_doc_fn])

        coll = self.document.entity(
            dir_id,
            [
                (PROV_TYPE, WFPROV["Artifact"]),
                (PROV_TYPE, PROV["Collection"]),
                (PROV_TYPE, PROV["Dictionary"]),
                (PROV_TYPE, RO["Folder"]),
            ],
        )

        if "basename" in value:
            coll.add_attributes({CWLPROV["basename"]: cast(str, value["basename"])})

        # ORE description of ro:Folder, saved separately
        coll_b = dir_bundle.entity(
            dir_id,
            [(PROV_TYPE, RO["Folder"]), (PROV_TYPE, ORE["Aggregation"])],
        )
        self.document.mentionOf(dir_id + "#ore", dir_id, dir_bundle.identifier)

        # dir_manifest = dir_bundle.entity(
        #     dir_bundle.identifier, {PROV["type"]: ORE["ResourceMap"],
        #                             ORE["describes"]: coll_b.identifier})

        coll_attribs: List[Tuple[Union[str, Identifier], Any]] = [
            (ORE["isDescribedBy"], dir_bundle.identifier)
        ]
        coll_b_attribs: List[Tuple[Union[str, Identifier], Any]] = []

        # FIXME: .listing might not be populated yet - hopefully
        # a later call to this method will sort that
        is_empty = True

        if "listing" not in value:
            get_listing(self.fsaccess, value)
        for entry in cast(MutableSequence[CWLObjectType], value.get("listing", [])):
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

            m_entity.add_attributes(
                {
                    PROV["pairKey"]: cast(str, entry["basename"]),
                    PROV["pairEntity"]: entity,
                }
            )

            # As well as a being a
            # http://wf4ever.github.io/ro/2016-01-28/ro/#FolderEntry
            m_b.add_asserted_type(RO["FolderEntry"])
            m_b.add_asserted_type(ORE["Proxy"])
            m_b.add_attributes(
                {
                    RO["entryName"]: cast(str, entry["basename"]),
                    ORE["proxyIn"]: coll,
                    ORE["proxyFor"]: entity,
                }
            )
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
        ore_doc_path = str(PurePosixPath(METADATA, ore_doc_fn))
        with self.research_object.write_bag_file(ore_doc_path) as provenance_file:
            ore_doc.serialize(provenance_file, format="rdf", rdf_format="turtle")
        self.research_object.add_annotation(dir_id, [ore_doc_fn], ORE["isDescribedBy"].uri)

        if is_empty:
            # Empty directory
            coll.add_asserted_type(PROV["EmptyCollection"])
            coll.add_asserted_type(PROV["EmptyDictionary"])
        self.research_object.add_uri(coll.identifier.uri)
        return coll

    def declare_string(self, value: str) -> Tuple[ProvEntity, str]:
        """Save as string in UTF-8."""
        byte_s = BytesIO(str(value).encode(ENCODING))
        data_file = self.research_object.add_data_file(byte_s, content_type=TEXT_PLAIN)
        checksum = PurePosixPath(data_file).name
        # FIXME: Don't naively assume add_data_file uses hash in filename!
        data_id = "data:%s" % PurePosixPath(data_file).stem
        entity = self.document.entity(
            data_id, {PROV_TYPE: WFPROV["Artifact"], PROV_VALUE: str(value)}
        )
        return entity, checksum

    def declare_artefact(self, value: Any) -> ProvEntity:
        """Create data artefact entities for all file objects."""
        if value is None:
            # FIXME: If this can happen in CWL, we'll
            # need a better way to represent this in PROV
            return self.document.entity(CWLPROV["None"], {PROV_LABEL: "None"})

        if isinstance(value, (bool, int, float)):
            # Typically used in job documents for flags

            # FIXME: Make consistent hash URIs for these
            # that somehow include the type
            # (so "1" != 1 != "1.0" != true)
            entity = self.document.entity(uuid.uuid4().urn, {PROV_VALUE: value})
            self.research_object.add_uri(entity.identifier.uri)
            return entity

        if isinstance(value, (str, str)):
            (entity, _) = self.declare_string(value)
            return entity

        if isinstance(value, bytes):
            # If we got here then we must be in Python 3
            byte_s = BytesIO(value)
            data_file = self.research_object.add_data_file(byte_s)
            # FIXME: Don't naively assume add_data_file uses hash in filename!
            data_id = "data:%s" % PurePosixPath(data_file).stem
            return self.document.entity(
                data_id,
                {PROV_TYPE: WFPROV["Artifact"], PROV_VALUE: str(value)},
            )

        if isinstance(value, MutableMapping):
            if "@id" in value:
                # Already processed this value, but it might not be in this PROV
                entities = self.document.get_record(value["@id"])
                if entities:
                    return cast(List[ProvEntity], entities)[0]
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
                coll_id,
                [
                    (PROV_TYPE, WFPROV["Artifact"]),
                    (PROV_TYPE, PROV["Collection"]),
                    (PROV_TYPE, PROV["Dictionary"]),
                ],
            )

            if value.get("class"):
                _logger.warning("Unknown data class %s.", value["class"])
                # FIXME: The class might be "http://example.com/somethingelse"
                coll.add_asserted_type(CWLPROV[value["class"]])

            # Let's iterate and recurse
            coll_attribs: List[Tuple[Union[str, Identifier], Any]] = []
            for key, val in value.items():
                v_ent = self.declare_artefact(val)
                self.document.membership(coll, v_ent)
                m_entity = self.document.entity(uuid.uuid4().urn)
                # Note: only support PROV-O style dictionary
                # https://www.w3.org/TR/prov-dictionary/#dictionary-ontological-definition
                # as prov.py do not easily allow PROV-N extensions
                m_entity.add_asserted_type(PROV["KeyEntityPair"])
                m_entity.add_attributes({PROV["pairKey"]: str(key), PROV["pairEntity"]: v_ent})
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
                uuid.uuid4().urn,
                [
                    (PROV_TYPE, WFPROV["Artifact"]),
                    (PROV_TYPE, PROV["Collection"]),
                ],
            )
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
            _logger.warning("Unrecognized type %s of %r", type(value), value)
            # Let's just fall back to Python repr()
            entity = self.document.entity(uuid.uuid4().urn, {PROV_LABEL: repr(value)})
            self.research_object.add_uri(entity.identifier.uri)
            return entity

    def used_artefacts(
        self,
        job_order: Union[CWLObjectType, List[CWLObjectType]],
        process_run_id: str,
        name: Optional[str] = None,
    ) -> None:
        """Add used() for each data artefact."""
        if isinstance(job_order, list):
            for entry in job_order:
                self.used_artefacts(entry, process_run_id, name)
        else:
            # FIXME: Use workflow name in packed.cwl, "main" is wrong for nested workflows
            base = "main"
            if name is not None:
                base += "/" + name
            for key, value in job_order.items():
                prov_role = self.wf_ns[f"{base}/{key}"]
                try:
                    entity = self.declare_artefact(value)
                    self.document.used(
                        process_run_id,
                        entity,
                        datetime.datetime.now(),
                        None,
                        {"prov:role": prov_role},
                    )
                except OSError:
                    pass

    def generate_output_prov(
        self,
        final_output: Union[CWLObjectType, MutableSequence[CWLObjectType], None],
        process_run_id: Optional[str],
        name: Optional[str],
    ) -> None:
        """Call wasGeneratedBy() for each output,copy the files into the RO."""
        if isinstance(final_output, MutableSequence):
            for entry in final_output:
                self.generate_output_prov(entry, process_run_id, name)
        elif final_output is not None:
            # Timestamp should be created at the earliest
            timestamp = datetime.datetime.now()

            # For each output, find/register the corresponding
            # entity (UUID) and document it as generated in
            # a role corresponding to the output
            for output, value in final_output.items():
                entity = self.declare_artefact(value)
                if name is not None:
                    name = urllib.parse.quote(str(name), safe=":/,#")
                    # FIXME: Probably not "main" in nested workflows
                    role = self.wf_ns[f"main/{name}/{output}"]
                else:
                    role = self.wf_ns["main/%s" % output]

                if not process_run_id:
                    process_run_id = self.workflow_run_uri

                self.document.wasGeneratedBy(
                    entity, process_run_id, timestamp, None, {"prov:role": role}
                )

    def prospective_prov(self, job: JobsType) -> None:
        """Create prospective prov recording as wfdesc prov:Plan."""
        if not isinstance(job, WorkflowJob):
            # direct command line tool execution
            self.document.entity(
                "wf:main",
                {
                    PROV_TYPE: WFDESC["Process"],
                    "prov:type": PROV["Plan"],
                    "prov:label": "Prospective provenance",
                },
            )
            return

        self.document.entity(
            "wf:main",
            {
                PROV_TYPE: WFDESC["Workflow"],
                "prov:type": PROV["Plan"],
                "prov:label": "Prospective provenance",
            },
        )

        for step in job.steps:
            stepnametemp = "wf:main/" + str(step.name)[5:]
            stepname = urllib.parse.quote(stepnametemp, safe=":/,#")
            provstep = self.document.entity(
                stepname,
                {PROV_TYPE: WFDESC["Process"], "prov:type": PROV["Plan"]},
            )
            self.document.entity(
                "wf:main",
                {
                    "wfdesc:hasSubProcess": provstep,
                    "prov:label": "Prospective provenance",
                },
            )
        # TODO: Declare roles/parameters as well

    def activity_has_provenance(self, activity: str, prov_ids: Sequence[Identifier]) -> None:
        """Add http://www.w3.org/TR/prov-aq/ relations to nested PROV files."""
        # NOTE: The below will only work if the corresponding metadata/provenance arcp URI
        # is a pre-registered namespace in the PROV Document
        attribs: List[Tuple[Union[str, Identifier], Any]] = [
            (PROV["has_provenance"], prov_id) for prov_id in prov_ids
        ]
        self.document.activity(activity, other_attributes=attribs)
        # Tip: we can't use https://www.w3.org/TR/prov-links/#term-mention
        # as prov:mentionOf() is only for entities, not activities
        uris = [i.uri for i in prov_ids]
        self.research_object.add_annotation(activity, uris, PROV["has_provenance"].uri)

    def finalize_prov_profile(self, name: Optional[str]) -> List[QualifiedName]:
        """Transfer the provenance related files to the RO."""
        # NOTE: Relative posix path
        if name is None:
            # main workflow, fixed filenames
            filename = "primary.cwlprov"
        else:
            # ASCII-friendly filename, avoiding % as we don't want %2520 in manifest.json
            wf_name = urllib.parse.quote(str(name), safe="").replace("%", "_")
            # Note that the above could cause overlaps for similarly named
            # workflows, but that's OK as we'll also include run uuid
            # which also covers thhe case of this step being run in
            # multiple places or iterations
            filename = f"{wf_name}.{self.workflow_run_uuid}.cwlprov"

        basename = str(PurePosixPath(PROVENANCE) / filename)

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
