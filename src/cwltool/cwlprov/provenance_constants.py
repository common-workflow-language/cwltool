import hashlib
import os
import uuid

from prov.identifier import Namespace

__citation__ = "https://doi.org/10.5281/zenodo.1208477"

# NOTE: Semantic versioning of the CWLProv Research Object
# **and** the cwlprov files
#
# Rough guide (major.minor.patch):
# 1. Bump major number if removing/"breaking" resources or PROV statements
# 2. Bump minor number if adding resources or PROV statements
# 3. Bump patch number for non-breaking non-adding changes,
#    e.g. fixing broken relative paths
CWLPROV_VERSION = "https://w3id.org/cwl/prov/0.6.0"

# Research Object folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")
LOGS = os.path.join(METADATA, "logs")
WFDESC = Namespace("wfdesc", "http://purl.org/wf4ever/wfdesc#")
WFPROV = Namespace("wfprov", "http://purl.org/wf4ever/wfprov#")
WF4EVER = Namespace("wf4ever", "http://purl.org/wf4ever/wf4ever#")
RO = Namespace("ro", "http://purl.org/wf4ever/ro#")
ORE = Namespace("ore", "http://www.openarchives.org/ore/terms/")
FOAF = Namespace("foaf", "http://xmlns.com/foaf/0.1/")
SCHEMA = Namespace("schema", "http://schema.org/")
CWLPROV = Namespace("cwlprov", "https://w3id.org/cwl/prov#")
ORCID = Namespace("orcid", "https://orcid.org/")
UUID = Namespace("id", "urn:uuid:")

# BagIt and YAML always use UTF-8
ENCODING = "UTF-8"
TEXT_PLAIN = f"text/plain; charset={ENCODING!r}"

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
