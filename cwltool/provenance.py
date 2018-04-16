from __future__ import absolute_import
import io
from io import open
import json
import re
import os
import os.path
import posixpath
import shutil
import tempfile
import itertools
import logging

import hashlib
# Old Python2 might not have these
try:
    from hashlib import sha256
except:
    sha256 = None
try:
    from hashlib import sha512
except:
    sha512 = None

from shutil import copyfile
import time
import copy
import datetime
import prov.model as provM
import prov.graph as graph
from prov.identifier import Namespace
from prov.model import PROV, ProvDocument, ProvActivity

# Disabled due to excessive transitive dependencies
#from networkx.drawing.nx_agraph import graphviz_layout
#from networkx.drawing.nx_pydot import write_dot
import uuid
from collections import OrderedDict

from six.moves import urllib

import graphviz
import networkx as nx
import ruamel.yaml as yaml
import warnings
from typing import Any, Dict, Set, List, Tuple, Text, Optional, IO, Callable, cast, Union
from subprocess import check_call
from schema_salad.sourceline import SourceLine


# This will need "pip install future" on Python 2 (!)
from past.builtins import basestring

from socket import getfqdn
from getpass import getuser
try:
    # pwd is only available on Unix
    from pwd import getpwnam
except:
    getpwnam = None

from .errors import WorkflowException
from .process import shortname
from .stdfsaccess import StdFsAccess


warnings.simplefilter('ignore', yaml.error.UnsafeLoaderWarning)
relativised_input_object={}  # type: Dict[str, Any]
_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")
WFDESC=Namespace("wfdesc", 'http://purl.org/wf4ever/wfdesc#')
WFPROV=Namespace("wfprov", 'http://purl.org/wf4ever/wfprov#')
FOAF=Namespace("foaf", 'http://xmlns.com/foaf/0.1/')
SCHEMA=Namespace("schema", 'http://schema.org/')
CWLPROV=Namespace('cwlprov', 'https://w3id.org/cwl/prov#')
ORCID=Namespace("orcid", "https://orcid.org/")
UUID=Namespace("id", "urn:uuid:")

# BagIt and YAML always use UTF-8
ENCODING="UTF-8"

# Citation for conformsTo
__citation__="https://doi.org/10.5281/zenodo.1208477"

# sha1, compatible with the File type's "checksum" field
# e.g. "checksum" = "sha1$47a013e660d408619d894b20806b1d5086aab03b"
# See ./cwltool/schemas/v1.0/Process.yml
hashmethod = hashlib.sha1

# TODO: Better identifiers for user, at least
# these should be preserved in ~/.config/cwl for every execution
# on this host
userUUID = uuid.uuid4().urn
accountUUID = uuid.uuid4().urn

def _convert_path(path, from_path=os.path, to_path=posixpath):
    # type: (str,Any,Any) -> str
    if from_path == to_path:
        return path
    if (from_path.isabs(path)):
        raise ValueError("path must be relative: %s" % path)
        # ..as it might include system paths like "C:\" or /tmp

    split = path.split(from_path.sep)

    converted = to_path.sep.join(split)
    return converted

def _posix_path(local_path):
    # type: (str) -> str
    return _convert_path(local_path, os.path, posixpath)

def _local_path(posix_path):
    # type: (str) -> str
    return _convert_path(posix_path, posixpath, os.path)

def _whoami():
    # type: () -> Tuple[str,str]
    """
    Return the current operating system account as (username, fullname)
    """
    username = getuser()
    fullname = username
    if getpwnam:
        p = getpwnam(username)
        if p:
            fullname = p.pw_gecos.split(",",1)[0]
    return (username, fullname)


class WritableBagFile(io.FileIO):
    def __init__(self, ro, rel_path):
        # type: (ResearchObject, str) -> None
        self.ro = ro
        if (posixpath.isabs(rel_path)):
            raise ValueError("rel_path must be relative: %s" % rel_path)
        self.rel_path = rel_path
        self.hashes = {"sha1": hashlib.sha1(),
                       "sha256": hashlib.sha256(),
                       "sha512": hashlib.sha512()}
        # Open file in RO folder
        path = os.path.abspath(os.path.join(ro.folder, _local_path(rel_path)))
        if not path.startswith(os.path.abspath(ro.folder)):
            raise ValueError("Path is outside Research Object: %s" % path)
        super(WritableBagFile, self).__init__(path, mode="w")

    def write(self, b):
        # type: (bytes) -> None
        super(WritableBagFile, self).write(b)
        for h in self.hashes.values():
            h.update(b)

    def close(self):
        # FIXME: Convert below block to a ResearchObject method?
        if self.rel_path.startswith("data/"):
            self.ro.bagged_size[self.rel_path] = self.tell()
        else:
            self.ro.tagfiles.add(self.rel_path)

        super(WritableBagFile, self).close()
        # { "sha1": "f572d396fae9206628714fb2ce00f72e94f2258f" }
        checksums = {}
        for name in self.hashes:
            checksums[name] = self.hashes[name].hexdigest().lower()
        self.ro.add_to_manifest(self.rel_path, checksums)

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
        # type: (Optional[int]) -> None
        # FIXME: This breaks contract io.IOBase,
        # as it means we would have to recalculate the hash
        if size is not None:
            raise IOError("WritableBagFile can't truncate")

def _valid_orcid(orcid): # type: (Text) -> Text
    """Ensure orcid is a valid ORCID identifier.

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
            ## alternative pattern, but probably messier
            ## r"^((https?://)?orcid.org/)?"

            # ORCID number is always 4x4 numerical digits,
            # but last digit (modulus 11 checksum)
            # can also be X (but we made it lowercase above).
            # e.g. 0000-0002-1825-0097
            # or   0000-0002-1825-009X
            r"(?P<orcid>(\d{4}-\d{4}-\d{4}-\d{3}[0-9x]))$",
        orcid)

    if not match:
        help_url=u"https://support.orcid.org/knowledgebase/articles/116780-structure-of-the-orcid-identifier"
        raise ValueError(u"Invalid ORCID: %s\n%s" % (orcid, help_url))

    # Conservative in what we produce:
    # a) Ensure any checksum digit is uppercase
    orcid_num = match.group("orcid").upper()
    # b) Re-add the official prefix https://orcid.org/
    return u"https://orcid.org/%s" % orcid_num

class ResearchObject():
    def __init__(self, tmpPrefix="tmp", orcid=None, full_name=None):
        # type: (str, str, str) -> None

        self.tmpPrefix = tmpPrefix
        self.orcid = _valid_orcid(orcid)
        if self.orcid:
            _logger.info(u"[provenance] Creator ORCID: %s", self.orcid)
        self.full_name = full_name or None
        if self.full_name:
            _logger.info(u"[provenance] Creator Full name: %s", self.full_name)
        self.folder = os.path.abspath(tempfile.mkdtemp(prefix=tmpPrefix))
        # map of filename "data/de/alsdklkas": 12398123 bytes
        self.bagged_size = {} #type: Dict
        self.tagfiles = set() #type: Set
        self._file_provenance = {} #type: Dict

        # These should be replaced by generate_provDoc when workflow/run IDs are known:
        self.engineUUID = "urn:uuid:%s" % uuid.uuid4()
        u = uuid.uuid4()
        self.workflowRunURI = u.urn
        self.base_uri = "arcp://uuid,%s/" % u
        self.wf_ns = Namespace("ex", "http://example.com/wf-%s#" % u)
        self.cwltoolVersion = "cwltool (unknown version)"
        ##
        # This function will be added by create_job()
        self.make_fs_access = None  # type: Callable[[Text], StdFsAccess]
        ##

        self._initialize()
        _logger.info(u"[provenance] Temporary research object: %s", self.folder)

    def _initialize(self):
        # type: (...) -> None
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))
        self._initialize_bagit()

    def _initialize_bagit(self):
        # type: (...) -> None
        # Write fixed bagit header
        bagit = os.path.join(self.folder, "bagit.txt")
        # encoding: always UTF-8 (although ASCII would suffice here)
        # newline: ensure LF also on Windows
        with open(bagit, "w", encoding = ENCODING, newline='\n') as bagitFile:
            # TODO: \n or \r\n ?
            bagitFile.write(u"BagIt-Version: 0.97\n")
            bagitFile.write(u"Tag-File-Character-Encoding: %s\n" % ENCODING)

    def _finalize(self):
        # type: () -> None
        self._write_ro_manifest()
        self._write_bag_info()

    def host_provenance(self, document):
        # type: (ProvDocument) -> None
        document.add_namespace(CWLPROV)
        document.add_namespace(UUID)
        document.add_namespace(FOAF)

        hostname = getfqdn()
        account = document.agent(accountUUID,{provM.PROV_TYPE: FOAF["OnlineAccount"],
            # won't have a foaf:accountServiceHomepage for unix hosts, but
            # we can at least provide hostname
            "prov:location": hostname,
            CWLPROV["hostname"]: hostname
        })

    def user_provenance(self, document):
        # type: (ProvDocument) -> None
        (username, fullname) = _whoami()

        if not self.full_name:
            self.full_name = fullname

        document.add_namespace(UUID)
        document.add_namespace(ORCID)
        document.add_namespace(FOAF)
        account = document.agent(accountUUID, {provM.PROV_TYPE: FOAF["OnlineAccount"],
            "prov:label": username,
            FOAF["accountName"]: username
        })
        user = document.agent(self.orcid or userUUID,
            {provM.PROV_TYPE: PROV["Person"],
            "prov:label": self.full_name,
            FOAF["name"]: self.full_name,
            FOAF["account"]: account,
            })
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
        # type: (str, str) -> IO

        # For some reason below throws BlockingIOError
        #fp = io.BufferedWriter(WritableBagFile(self, path))
        fp = cast(IO, WritableBagFile(self, path))
        if encoding:
            # encoding: match Tag-File-Character-Encoding: UTF-8
            # newline: ensure LF also on Windows
            return cast(IO,
                io.TextIOWrapper(fp, encoding=encoding, newline="\n"))
        else:
            return fp

    def add_tagfile(self, path, when=None):
        # type: (str, datetime.datetime) -> None
        checksums = {}
        # Read file to calculate its checksum
        with open(path, "rb") as fp:
            # FIXME: Should have more efficient open_tagfile() that
            # does all checksums in one go while writing through,
            # adding checksums after closing.
            # Below probably OK for now as metadata files
            # are not too large..?

            checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)
            fp.seek(0)
            # Older Python's might not have all checksums
            if sha256:
                fp.seek(0)
                checksums["sha256"]= self._checksum_copy(fp, hashmethod=sha256)
            if sha512:
                fp.seek(0)
                checksums["sha512"]= self._checksum_copy(fp, hashmethod=sha512)
        rel_path = _posix_path(os.path.relpath(path, self.folder))
        self.tagfiles.add(rel_path)
        self.add_to_manifest(rel_path, checksums)
        if when:
            self._file_provenance[rel_path] = {"createdOn" : when.isoformat()}

    def _ro_aggregates(self):
        # type: () -> List[Dict[str,Any]]
        aggregates = []
        for path in self.bagged_size.keys():
            a = {}  # type: Dict[str,Any]

            (folder,f) = posixpath.split(path)

            # NOTE: Here we end up aggregating the abstract
            # data items by their sha1 hash, so that it matches
            # the entity() in the prov files.

            # TODO: Change to nih:sha-256; hashes
            #  https://tools.ietf.org/html/rfc6920#section-7
            a["uri"] = 'urn:hash::sha1:' + f
            a["bundledAs"] = {
                # The arcp URI is suitable ORE proxy; local to this RO.
                # (as long as we don't also aggregate it by relative path!)
                "uri": self.base_uri + path,
                # relate it to the data/ path
                "folder": "/%s/" % folder,
                "filename": f,
            }
            if path in self._file_provenance:
                # Made by workflow run, merge captured provenance
                a["bundledAs"].update(self._file_provenance[path])
            else:
                # Probably made outside wf run, part of job object?
                pass
            aggregates.append(a)

        for path in self.tagfiles:
            if (not (path.startswith(METADATA) or path.startswith(WORKFLOW) or
                path.startswith(SNAPSHOT))):
                # probably a bagit file
                continue
            if path == posixpath.join(METADATA, "manifest.json"):
                # Should not really be there yet! But anyway, we won't
                # aggregate it.
                continue

            a = {}
            # These are local paths like metadata/provenance - but
            # we need to relativize them for our current directory for
            # as we are saved in metadata/manifest.json
            uri = posixpath.relpath(path, METADATA)

            a["uri"] = uri
            a.update(self._guess_mediatype(path))

            if path in self._file_provenance:
                # Propagate file provenance (e.g. timestamp)
                a.update(self._file_provenance[path])
            elif not path.startswith(SNAPSHOT):
                # make new timestamp?
                a.update(self._self_made())
            aggregates.append(a)
        return aggregates

    def _guess_mediatype(self, rel_path):
        # type: (str) -> Optional[Dict[str,str]]
        MEDIA_TYPES = {
            # Adapted from
            # https://w3id.org/bundle/2014-11-05/#media-types

            "txt":    'text/plain; charset="UTF-8"',
            "ttl":    'text/turtle; charset="UTF-8"',
            "rdf":    'application/rdf+xml',
            "json":   'application/json',
            "jsonld": 'application/ld+json',
            "xml":    'application/xml',
            ##
            "cwl":    'text/x+yaml; charset="UTF-8"',
            "provn":  'text/provenance-notation; charset="UTF-8"',
            "nt":     'application/n-triples',
        }
        CONFORMS_TO = {
            "provn":  'http://www.w3.org/TR/2013/REC-prov-n-20130430/',
            "cwl":    'https://w3id.org/cwl/',
        }

        PROV_CONFORMS_TO = {
            "provn":  'http://www.w3.org/TR/2013/REC-prov-n-20130430/',
            "rdf":    'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
            "ttl":    'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
            "nt":     'http://www.w3.org/TR/2013/REC-prov-o-20130430/',
            "jsonld": 'http://www.w3.org/TR/2013/REC-prov-o-20130430/',

            "xml":    'http://www.w3.org/TR/2013/NOTE-prov-xml-20130430/',
            "json":   'http://www.w3.org/Submission/2013/SUBM-prov-json-20130424/',
        }


        extension = rel_path.rsplit(".", 1)[-1].lower()
        if extension == rel_path:
            # No ".", no extension
            extension = None

        a = {} # type: Dict[str, Any]
        if extension in MEDIA_TYPES:
            a["mediatype"] = MEDIA_TYPES[extension]

        if extension in CONFORMS_TO:
            # TODO: Open CWL file to read its declared "cwlVersion", e.g.
            # cwlVersion = "v1.0"
            a["conformsTo"] = CONFORMS_TO[extension]

        if (rel_path.startswith(_posix_path(PROVENANCE))
            and extension in PROV_CONFORMS_TO):
            if ".cwlprov" in rel_path:
                # Our own!
                a["conformsTo"] = [PROV_CONFORMS_TO[extension], __citation__]
            else:
                # Some other PROV
                # TODO: Recognize ProvOne etc.
                a["conformsTo"] = PROV_CONFORMS_TO[extension]
        return a

    def _ro_annotations(self):
        # type: () -> List[Dict]
        annotations = []
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.workflowRunURI,
            "content": "/",
            # https://www.w3.org/TR/annotation-vocab/#named-individuals
            "oa:motivatedBy": { "@id": "oa:describing"}
        })

        # How was it run?
        prov_files = [posixpath.relpath(p, METADATA)
            for p in self.tagfiles if p.startswith(_posix_path(PROVENANCE))]
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.workflowRunURI,
            "content": prov_files,
            # Modulation of https://www.w3.org/TR/prov-aq/
            "oa:motivatedBy": { "@id": "http://www.w3.org/ns/prov#has_provenance"}
        })

        # Where is the main workflow?
        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": posixpath.join(WORKFLOW, "packed.cwl"),
            "oa:motivatedBy": { "@id": "oa:highlighting"}
        })

        annotations.append({
            "uri": uuid.uuid4().urn,
            "about": self.workflowRunURI,
            "content": [posixpath.join(WORKFLOW, "packed.cwl"),
                        posixpath.join(WORKFLOW, "primary-job.json")],
            "oa:motivatedBy": { "@id": "oa:linking"}
        })


        return annotations

    def _authoredBy(self):
        # type: () -> Dict
        authoredBy = {}
        if self.orcid:
            authoredBy["orcid"] = self.orcid
        if self.full_name:
            authoredBy["name"] = self.full_name
            if not self.orcid:
                authoredBy["uri"] = userUUID

        if authoredBy:
            return {"authoredBy": authoredBy}
        else:
            # No point to claim it's authoredBy {}
            return {}


    def _write_ro_manifest(self):
        # type: () -> None

        # Does not have to be this order, but it's nice to be consistent
        manifest = OrderedDict() # type: Dict[str,Any]
        manifest["@context"] = [
                {"@base": "%s%s/" % (self.base_uri, _posix_path(METADATA)) },
                "https://w3id.org/bundle/context"
            ]
        manifest["id"] = "/"
        filename = "manifest.json"
        manifest["manifest"] = filename
        manifest.update(self._self_made())
        manifest.update(self._authoredBy())

        manifest["aggregates"] = self._ro_aggregates()
        manifest["annotations"] = self._ro_annotations()

        j = json.dumps(manifest, indent=4, ensure_ascii=False)
        rel_path = posixpath.join(_posix_path(METADATA), filename)
        with self.write_bag_file(rel_path) as fp:
            fp.write(j + "\n")

    def _write_bag_info(self):
        # type: () -> None

        with self.write_bag_file("bag-info.txt") as infoFile:
            infoFile.write(u"Bag-Software-Agent: %s\n" % self.cwltoolVersion)
            # FIXME: require sha-512 of payload to comply with profile?
            # FIXME: Update profile
            infoFile.write(u"BagIt-Profile-Identifier: https://w3id.org/ro/bagit/profile\n")
            infoFile.write(u"Bagging-Date: %s\n" % datetime.date.today().isoformat())
            infoFile.write(u"External-Description: Research Object of CWL workflow run\n")
            if self.full_name:
                infoFile.write(u"Contact-Name: %s\n" % self.full_name)

            # NOTE: We can't use the urn:uuid:{UUID} of the workflow run (a prov:Activity)
            # as identifier for the RO/bagit (a prov:Entity). However the arcp base URI is good.
            infoFile.write(u"External-Identifier: %s\n" % self.base_uri)

            # Calculate size of data/ (assuming no external fetch.txt files)
            totalSize = sum(self.bagged_size.values())
            numFiles = len(self.bagged_size)
            infoFile.write(u"Payload-Oxum: %d.%d\n" % (totalSize, numFiles))
        _logger.info(u"[provenance] Generated bagit metadata: %s", self.folder)

    def generate_provDoc(self, document, cwltoolVersion, engineUUID, workflowRunUUID):
        # type: (ProvDocument, str, str, Union[str,uuid.UUID]) -> str
        '''
        add basic namespaces
        '''
        # For consistent formatting, ensure it's a valid UUID instance
        if not isinstance(workflowRunUUID, uuid.UUID):
            workflowRunUUID = uuid.UUID(str(workflowRunUUID))

        self.cwltoolVersion = cwltoolVersion
        document.add_namespace('wfprov', 'http://purl.org/wf4ever/wfprov#')
        #document.add_namespace('prov', 'http://www.w3.org/ns/prov#')
        document.add_namespace('wfdesc', 'http://purl.org/wf4ever/wfdesc#')
        # TODO: Make this ontology. For now only has cwlprov:image
        document.add_namespace('cwlprov', 'https://w3id.org/cwl/prov#')
        document.add_namespace('foaf', 'http://xmlns.com/foaf/0.1/')
        document.add_namespace('schema', 'http://schema.org/')
        document.add_namespace('orcid', 'https://orcid.org/')
        document.add_namespace('id', 'urn:uuid:')
        # NOTE: Internet draft expired 2004-03-04 (!)
        #  https://tools.ietf.org/html/draft-thiemann-hash-urn-01
        # TODO: Change to nih:sha-256; hashes
        #  https://tools.ietf.org/html/rfc6920#section-7
        document.add_namespace('data', 'urn:hash::sha1:')
        # Also needed for docker images
        document.add_namespace("sha256", "nih:sha-256;")
        self.workflowRunURI = workflowRunUUID.urn
        # https://tools.ietf.org/id/draft-soilandreyes-arcp
        self.base_uri = "arcp://uuid,%s/" % workflowRunUUID
        ## info only, won't really be used by prov as sub-resources use /
        document.add_namespace('researchobject', self.base_uri)
        roIdentifierWorkflow= self.base_uri + "workflow/packed.cwl#"
        self.wf_ns = document.add_namespace("wf", roIdentifierWorkflow)
        roIdentifierInput=self.base_uri + "workflow/primary-job.json#"
        document.add_namespace("input", roIdentifierInput)
        self.engineUUID = engineUUID

        # More info about the account (e.g. username, fullname)
        # may or may not have been previously logged by user_provenance()
        # .. but we always know cwltool was launched (directly or indirectly)
        # by a user account, as cwltool is a command line tool
        account = document.agent(accountUUID)
        if self.orcid or self.full_name:
            person = {provM.PROV_TYPE: PROV["Person"], "prov:type": SCHEMA["Person"]}
            if self.full_name:
                person["prov:label"] = self.full_name
                person["foaf:name"] = self.full_name
                person["schema:name"] = self.full_name
            else:
                # TODO: Look up name from ORCID API?
                pass

            a = document.agent(self.orcid or uuid.uuid4().urn,
                               person)
            document.actedOnBehalfOf(account, a)

        # The execution of cwltool
        wfengine = document.agent(engineUUID, {provM.PROV_TYPE: PROV["SoftwareAgent"],
            "prov:type": WFPROV["WorkflowEngine"],
            "prov:label": cwltoolVersion})

        # FIXME: This datetime will be a bit too delayed, we should
        # capture when cwltool.py earliest started?
        document.wasStartedBy(wfengine, None, account, datetime.datetime.now())


        #define workflow run level activity
        document.activity(self.workflowRunURI, datetime.datetime.now(), None, {
            provM.PROV_TYPE: WFPROV["WorkflowRun"], "prov:label": "Run of workflow/packed.cwl#main"})
        #association between SoftwareAgent and WorkflowRun
        # FIXME: Below assumes main workflow always called "#main",
        # is this always true after packing?
        mainWorkflow = "wf:main"
        document.wasAssociatedWith(self.workflowRunURI, engineUUID, mainWorkflow)
        document.wasStartedBy(self.workflowRunURI, None, engineUUID, datetime.datetime.now())
        return self.workflowRunURI


    def snapshot_generation(self, ProvDep):
        # type: (Dict[str,str]) -> None
        '''
        Copies all the cwl files involved in this workflow run to snapshot
        directory
        '''

        for key, value in ProvDep.items():
            if key == "location" and value.split("/")[-1]:
                filename= value.split("/")[-1]
                path = os.path.join(self.folder, SNAPSHOT, filename)
                filepath=''
                if "file://" in value:
                    filepath=value[7:]
                else:
                    filepath=value

                # FIXME: What if destination path already exists?
                if os.path.exists(filepath):
                    shutil.copy(filepath, path)
                    when = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                    self.add_tagfile(path, when)
            elif key == "secondaryFiles" or key == "listing":
                for files in value:
                    if isinstance(files, dict):
                        self.snapshot_generation(files)
            else:
                pass

    def packed_workflow(self, packed):
        '''
        packs workflow and commandline tools to generate re-runnable workflow object in RO
        '''

        rel_path = posixpath.join(_posix_path(WORKFLOW), "packed.cwl")
        # Write as binary
        with self.write_bag_file(rel_path, encoding=None) as f:
            # YAML is always UTF8, but json.dumps gives us str in py2
            f.write(packed.encode(ENCODING))
        _logger.info(u"[provenance] Added packed workflow: %s", rel_path)

    def _checksum_copy(self, fp, copy_to_fp=None,
                       hashmethod=hashmethod, buffersize=1024*1024):
        # type: (IO, Optional[IO], Callable[[], Any], int) -> str

        # TODO: Use hashlib.new(hashmethod_str) instead?
        checksum = hashmethod()
        contents = fp.read(buffersize)
        while contents != b"":
            if copy_to_fp is not None:
                copy_to_fp.write(contents)
            checksum.update(contents)
            contents = fp.read(buffersize)
        if copy_to_fp is not None:
            copy_to_fp.flush()
        return checksum.hexdigest().lower()


    def add_data_file(self, from_fp, when=None):
        # type: (IO, Optional[datetime.datetime]) -> str
        '''
        copies inputs to Data
        '''
        with tempfile.NamedTemporaryFile(
                prefix=self.tmpPrefix, delete=False) as tmp:
            checksum = self._checksum_copy(from_fp, tmp)

        # Calculate hash-based file path
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
        if hashmethod == hashlib.sha1:
            self._add_to_bagit(rel_path, sha1=checksum)
        else:
            _logger.warning(u"[provenance] Unknown hash method %s for bagit manifest",
                hashmethod)
            # Inefficient, bagit support need to checksum again
            self._add_to_bagit(rel_path)
        _logger.info(u"[provenance] Added data file %s", path)
        if when:
            self._file_provenance[rel_path] = self._self_made(when)
        _logger.info(u"[provenance] Relative path for data file %s", rel_path)
        return rel_path

    def _self_made(self, when=None):
        # type: (Optional[datetime.datetime]) -> Dict[str,Any]
        if when is None:
            when = datetime.datetime.now()
        return {
                "createdOn": when.isoformat(),
                "createdBy": { "uri": self.engineUUID,
                               "name": self.cwltoolVersion
                             }
                }

    def add_to_manifest(self, rel_path, checksums):
        # type: (str, Dict[str,str]) -> None

        if (posixpath.isabs(rel_path)):
            raise ValueError("rel_path must be relative: %s" % rel_path)

        if (posixpath.commonprefix(["data/", rel_path]) == "data/"):
            # payload file, go to manifest
            manifest = "manifest"
        else:
            # metadata file, go to tag manifest
            manifest = "tagmanifest"

        # Add checksums to corresponding manifest files
        for (method,hash) in checksums.items():
            # File not in manifest because we bailed out on
            # existence in bagged_size above
            manifestpath = os.path.join(self.folder,
                "%s-%s.txt" % (manifest, method.lower()))
            # encoding: match Tag-File-Character-Encoding: UTF-8
            # newline: ensure LF also on Windows
            with open(manifestpath, "a", encoding=ENCODING, newline='\n') as checksumFile:
                line = u"%s  %s\n" % (hash, rel_path)
                _logger.debug(u"[provenance] Added to %s: %s", manifestpath, line)
                checksumFile.write(line)


    def _add_to_bagit(self, rel_path, **checksums):
        # type: (str, Any) -> None
        if (posixpath.isabs(rel_path)):
            raise ValueError("rel_path must be relative: %s" % rel_path)
        local_path = os.path.join(self.folder, _local_path(rel_path))
        if not os.path.exists(local_path):
            raise IOError("File %s does not exist within RO: %s" % (rel_path, local_path))

        if (rel_path in self.bagged_size):
            # Already added, assume checksum OK
            return
        self.bagged_size[rel_path] = os.path.getsize(local_path)

        if "sha1" not in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(local_path, "rb") as fp:
                # FIXME: Need sha-256 / sha-512 as well for RO BagIt profile?
                checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)

        self.add_to_manifest(rel_path, checksums)

    def create_job(self, job, make_fs_access, kwargs):
        # type: (Dict, Callable[[Text], StdFsAccess], Dict[str,Any]) -> Tuple[Dict,Dict]

        #TODO handle nested workflow at level 2 provenance
        #TODO customise the file
        '''
        This function takes the dictionary input object and generates
        a json file containing the relative paths and link to the associated
        cwl document
        '''
        self.make_fs_access = make_fs_access
        relativised_input_objecttemp2={} # type: Dict[Any,Any]
        relativised_input_objecttemp={}  # type: Dict[Any,Any]
        self._relativise_files(job, kwargs, relativised_input_objecttemp2)

        rel_path = posixpath.join(_posix_path(WORKFLOW), "primary-job.json")
        j = json.dumps(job, indent=4, ensure_ascii=False)
        with self.write_bag_file(rel_path) as fp:
            fp.write(j + u"\n")
        _logger.info(u"[provenance] Generated customised job file: %s", rel_path)

        #Generate dictionary with keys as workflow level input IDs and values as
        #1) for files the relativised location containing hash
        #2) for other attributes, the actual value.
        relativised_input_objecttemp={}
        for key, value in job.items():
            if isinstance(value, dict):
                if value.get("class") == "File":
                    relativised_input_objecttemp[key]=value
            else:
                relativised_input_objecttemp[key]=value
        relativised_input_object.update({k: v for k, v in relativised_input_objecttemp.items() if v})
        return relativised_input_object, relativised_input_objecttemp2

    def _relativise_files(self, structure, kwargs, relativised_input_objecttemp2):
        # type: (Any, Dict, Dict) -> None
        '''
        save any file objects into RO and update the local paths
        '''
        # Base case - we found a File we need to update
        _logger.debug(u"[provenance] Relativising: %s", structure)
        if isinstance(structure, dict):
            if structure.get("class") == "File":
                #standardised fs access object creation
                fsaccess = self.make_fs_access("")
                # TODO: Replace location/path with new add_data_file() paths
                with fsaccess.open(structure["location"], "rb") as f:
                    relative_path=self.add_data_file(f)
                    ref_location=structure["location"]
                    structure["location"]= "../"+relative_path
                    if not "checksum" in structure:
                        # FIXME: This naively relies on add_data_file setting hash as filename
                        structure["checksum"] = "sha1$%s" % posixpath.basename(relative_path)
                    relativised_input_objecttemp2[ref_location] = structure["location"]

            for o in structure.values():
                self._relativise_files(o, kwargs, relativised_input_objecttemp2)
            return

        if isinstance(structure, basestring):
            # Just a string value, no need to iterate further
            return
        try:
            for o in iter(structure):
                # Recurse and rewrite any nested File objects
                self._relativise_files(o, kwargs, relativised_input_objecttemp2)
        except TypeError:
            pass

    def finalize_provProfile(self, document):
        # type: (ProvDocument) -> None
        '''
        Transfer the provenance related files to RO
        '''
        self.prov_document = document
        # TODO: Generate filename per workflow run also for nested workflows
        # nested-47b74496-9ffd-42e4-b1ad-9a10fc93b9ce-cwlprov.provn
        # NOTE: Relative posix path
        basename = posixpath.join(_posix_path(PROVENANCE), "primary.cwlprov")
        # TODO: Also support other profiles than CWLProv, e.g. ProvOne

        # https://www.w3.org/TR/prov-xml/
        with self.write_bag_file(basename + ".xml") as fp:
            document.serialize(fp, format="xml", indent=4)

        # https://www.w3.org/TR/prov-n/
        with self.write_bag_file(basename + ".provn") as fp:
            document.serialize(fp, format="provn", indent=2)


        # https://www.w3.org/Submission/prov-json/
        with self.write_bag_file(basename + ".json") as fp:
            document.serialize(fp, format="json", indent=2)

        # "rdf" aka https://www.w3.org/TR/prov-o/
        # which can be serialized to ttl/nt/jsonld (and more!)

        # https://www.w3.org/TR/turtle/
        with self.write_bag_file(basename + ".ttl") as fp:
            document.serialize(fp, format="rdf", rdf_format="turtle")

        # https://www.w3.org/TR/n-triples/
        with self.write_bag_file(basename + ".nt") as fp:
            document.serialize(fp, format="rdf", rdf_format="ntriples")

        # https://www.w3.org/TR/json-ld/
        # TODO: Use a nice JSON-LD context
        # see also https://eprints.soton.ac.uk/395985/
        # 404 Not Found on https://provenance.ecs.soton.ac.uk/prov.jsonld :(
        with self.write_bag_file(basename + ".jsonld") as fp:
            document.serialize(fp, format="rdf", rdf_format="json-ld")

        _logger.info("[provenance] added all tag files")

    def startProcess(self, r, document, engineUUID, WorkflowRunID):
            # type: (Any, ProvDocument, str, str) -> None
            ## FIXME: What is the real name and type of r?
            ## process.py/workflow.py just says "Any" or "Generator"..
            '''
            record start of each step
            '''
            ProcessRunID=uuid.uuid4().urn
            #each subprocess is defined as an activity()
            ProcessName= urllib.parse.quote(str(r.name), safe=":/,#")
            provLabel="Run of workflow/packed.cwl#main/"+ProcessName
            ProcessProvActivity = document.activity(ProcessRunID, None, None, {provM.PROV_TYPE: WFPROV["ProcessRun"], "prov:label": provLabel})

            if hasattr(r, 'name') and ".cwl" not in getattr(r, "name") and "workflow main" not in getattr(r, "name"):
                document.wasAssociatedWith(ProcessRunID, engineUUID, str("wf:main/"+ProcessName))
            document.wasStartedBy(ProcessRunID, None, WorkflowRunID, datetime.datetime.now(), None, None)
            return ProcessProvActivity

    def declare_artefact(self, relativised_input_object, document, job_order_object):
        # type: (Any, ProvDocument, Dict) -> None
        '''
        create data artefact entities for all file objects.
        '''
        if isinstance(relativised_input_object, dict):
            # Base case - we found a File we need to update
            if relativised_input_object.get("class") == "File":
                #create an artefact
                shahash="data:"+relativised_input_object["location"].split("/")[-1]
                document.entity(shahash, {provM.PROV_TYPE:WFPROV["Artifact"]})

            for o in relativised_input_object.values():
                self.declare_artefact(o, document, job_order_object)
            return

        if isinstance(relativised_input_object, basestring):
            # Just a string value, no need to iterate further
            # FIXME: Should these be added as PROV entities as well?
            return

        try:
            for o in iter(relativised_input_object):
                # Recurse and rewrite any nested File objects
                self.declare_artefact(o, document, job_order_object)
        except TypeError:
            pass


    def generate_outputProv(self, final_output, document, WorkflowRunID=None, ProcessRunID=None, name=None):
        # type: (Dict, ProvDocument, str, str, str) -> None
        '''
        create wasGeneratedBy() for each output and copy each output file in the RO
        '''
        ## A bit too late, but we don't know the "inner" when
        when = datetime.datetime.now()
        key_files=[] # type: List[List[Any]]
        for key, value in final_output.items():

            if isinstance(value, list):
                key_files.append(self.array_output(key, value))
            elif isinstance (value, dict):
                key_files.append(self.dict_output(key, value))

        merged_total= list(itertools.chain.from_iterable(key_files))

        #generate data artefacts at workflow level
        for tuple_entry in merged_total:
            # FIXME: What are these magic array[][] positions???
            output_checksum="data:"+str(tuple_entry[1][5:])

            if ProcessRunID:
                name = urllib.parse.quote(name, safe=":/,#")
                stepProv = self.wf_ns["main"+"/"+name+"/"+str(tuple_entry[0])]

                document.entity(output_checksum, {provM.PROV_TYPE: WFPROV["Artifact"]})
                document.wasGeneratedBy(output_checksum, ProcessRunID, when, None, {"prov:role":stepProv})
            else:
                outputProvRole = self.wf_ns["main"+"/"+str(tuple_entry[0])]
                document.entity(output_checksum, {provM.PROV_TYPE:WFPROV["Artifact"]})
                document.wasGeneratedBy(output_checksum, WorkflowRunID, when, None, {"prov:role":outputProvRole })
                # FIXME: What are these magic array positions???
                with open(tuple_entry[2][7:], "rb") as fp:
                    rel_path = self.add_data_file(fp, when)
                    _logger.info(u"[provenance] Adding output file %s to RO", rel_path)

    def array_output(self, key, current_l):
        # type: (Any, List) -> List
        '''
        helper function for generate_outputProv()
        for the case when we have an array of files as output
        '''
        new_l=[]
        for y in current_l:
            if isinstance(y, dict):
                new_l.append((key, y['checksum'], y['location']))

        return new_l

    def dict_output(self, key, current_dict):
        # type: (Any, Dict) -> List
        '''
        helper function for generate_outputProv()
        for the case when the output is key:value where value is a file item
        '''
        new_d = []
        if current_dict.get("class") == "File":
            new_d.append((key, current_dict['checksum'], current_dict['location']))
        return new_d

    def used_artefacts(self, job_order, ProcessProvActivity, document, reference_locations, name):
        # type: (Dict, Any, ProvDocument, ProvActivity, str) -> None
        '''
        adds used() for each data artefact
        '''
        for key, value in job_order.items():
            provRole = self.wf_ns["main/%s/%s" % (name, key)]
            ProcessRunID=str(ProcessProvActivity.identifier)
            if isinstance(value, dict) and 'location' in value:
                location=str(value['location'])
                #filename=location.split("/")[-1]
                filename=posixpath.basename(location)

                if 'checksum' in value:
                    c = value['checksum']
                    _logger.info("[provenance] Used data w/ checksum %s", c)
                    (method, checksum) = value['checksum'].split("$", 1)
                    if (method == "sha1"):
                        document.used(ProcessRunID, "data:%s" % checksum, datetime.datetime.now(),None, {"prov:role":provRole })
                        return # successfully logged
                    else:
                        _logger.warn("[provenance] Unknown checksum algorithm %s", method)
                        pass
                else:
                    _logger.info("[provenance] Used data w/o checksum %s", location)
                    # FIXME: Store manually
                    pass

                # If we made it here, then we didn't log it correctly with checksum above,
                # we'll have to hash it again (and potentially add it to RO)
                # TODO: Avoid duplication of code here and in
                # _relativise_files()
                # TODO: check we don't double-hash everything now
                fsaccess = self.make_fs_access("")
                with fsaccess.open(location, "rb") as f:
                    relative_path=self.add_data_file(f)
                    checksum = posixpath.basename(relative_path)
                    document.used(ProcessRunID, "data:%s" % checksum, datetime.datetime.now(),None, {"prov:role":provRole })

            else:  # add the actual data value in the prov document
                # Convert to bytes so we can get a hash (and add to RO)
                b = io.BytesIO(str(value).encode(ENCODING))
                data_file = self.add_data_file(b)
                # FIXME: Don't naively assume add_data_file uses hash in filename!
                data_id="data:%s" % posixpath.split(data_file)[1]
                document.entity(data_id, {provM.PROV_TYPE:WFPROV["Artifact"], provM.PROV_VALUE:str(value)})
                document.used(ProcessRunID, data_id, datetime.datetime.now(),None, {"prov:role":provRole })

    def copy_job_order(self, r, job_order_object):
        # type: (Any,Any) -> Any
        '''
        creates copy of job object for provenance
        '''
        if not hasattr(r, "tool"):
            # direct command line tool execution
            return job_order_object
        customised_job={} #new job object for RO
        for e, i in enumerate(r.tool["inputs"]):
            with SourceLine(r.tool["inputs"], e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                iid = shortname(i["id"])
                if iid in job_order_object:
                    customised_job[iid]= copy.deepcopy(job_order_object[iid]) #add the input element in dictionary for provenance
                elif "default" in i:
                    customised_job[iid]= copy.deepcopy(i["default"]) #add the defualt elements in the dictionary for provenance
                else:
                    raise WorkflowException(
                        u"Input '%s' not in input object and does not have a default value." % (i["id"]))
        return customised_job

    def prospective_prov(self, document, r):
        # type: (ProvDocument,Any) -> None
        '''
        create prospective provenance recording for the workflow as wfdesc prov:Plan
        '''
        if not hasattr(r, "steps"):
            # direct command line tool execution
            document.entity("wf:main", {provM.PROV_TYPE: WFDESC["Process"], "prov:type": PROV["Plan"], "prov:label":"Prospective provenance"})
            return

        # FIXME: Workflow is always called "#main"?
        document.entity("wf:main", {provM.PROV_TYPE: WFDESC["Workflow"], "prov:type": PROV["Plan"], "prov:label":"Prospective provenance"})

        steps=[]
        for s in r.steps:
            # FIXME: Use URI fragment identifier for step name, e.g. for spaces
            stepnametemp="wf:main/"+str(s.name)[5:]
            stepname=urllib.parse.quote(stepnametemp, safe=":/,#")
            steps.append(stepname)
            step = document.entity(stepname, {provM.PROV_TYPE: WFDESC["Process"], "prov:type": PROV["Plan"]})
            document.entity("wf:main", {"wfdesc:hasSubProcess":step, "prov:label":"Prospective provenance"})

        # TODO: Declare roles/parameters as well


#**************************************

    def close(self, saveTo=None):
        # type: (Optional[str]) -> None
        """Close the Research Object, optionally saving to specified folder.

        Closing will remove any temporary files used by this research object.
        After calling this method, this ResearchObject instance can no longer
        be used, except for no-op calls to .close().

        The 'saveTo' folder should not exist - if it does, it will be deleted.

        It is safe to call this function multiple times without the
        'saveTo' argument, e.g. within a try..finally block to
        ensure the temporary files of this RO are removed.
        """
        if saveTo is None:
            if self.folder:
                _logger.info(u"[provenance] Deleting temporary %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            saveTo = os.path.abspath(saveTo)
            _logger.info(u"[provenance] Finalizing Research Object")
            self._finalize()  # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(saveTo):
                _logger.info(u"[provenance] Deleting existing %s", saveTo)
                shutil.rmtree(saveTo)

            shutil.move(self.folder, saveTo)
            _logger.info(u"[provenance] Research Object saved to %s", saveTo)
        # Forget our temporary folder, which should no longer exists
        # This makes later close() a no-op
        self.folder = None

def create_researchObject(tmpPrefix,orcid=None,full_name=None):
    # type: (str,Optional[str],Optional[str]) -> ResearchObject
    return ResearchObject(tmpPrefix, orcid, full_name)
