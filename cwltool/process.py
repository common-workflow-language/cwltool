from __future__ import absolute_import

import abc
import copy
import errno
import functools
import hashlib
import json
import logging
import os
import shutil
import stat
import tempfile
import textwrap
import uuid
from collections import Iterable  # pylint: disable=unused-import
from io import open
from typing import (Any, Callable, Dict, Generator, Iterator, List,
                    Mapping, MutableMapping, MutableSequence, Optional, Set, Tuple,
                    Union, cast)

from pkg_resources import resource_stream
from rdflib import Graph  # pylint: disable=unused-import
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from six import PY3, iteritems, itervalues, string_types, with_metaclass
from six.moves import urllib
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text)
from schema_salad import schema, validate
from schema_salad.ref_resolver import Loader, file_uri
from schema_salad.sourceline import SourceLine, strip_dup_lineno

from . import expression
from .builder import Builder, HasReqsHints
from .context import LoadingContext  # pylint: disable=unused-import
from .context import RuntimeContext, getdefault
from .errors import UnsupportedRequirement, WorkflowException
from .loghandler import _logger
from .mutation import MutationManager  # pylint: disable=unused-import
from .pathmapper import (PathMapper, adjustDirObjs, ensure_writable,
                         get_listing, normalizeFilesDirs, visit_class)
from .secrets import SecretStore  # pylint: disable=unused-import
from .software_requirements import (  # pylint: disable=unused-import
    DependenciesConfiguration)
from .stdfsaccess import StdFsAccess
from .utils import (DEFAULT_TMP_PREFIX, aslist, cmp_like_py2,
                    copytree_with_merge, onWindows, random_outdir)
from .validate_js import validate_js_expressions
try:
    from os import scandir  # type: ignore
except ImportError:
    from scandir import scandir  # type: ignore
if TYPE_CHECKING:
    from .provenance import ProvenanceProfile  # pylint: disable=unused-import


class LogAsDebugFilter(logging.Filter):
    def __init__(self, name, parent):  # type: (Text, logging.Logger) -> None
        name = str(name)
        super(LogAsDebugFilter, self).__init__(name)
        self.parent = parent

    def filter(self, record):
        return self.parent.isEnabledFor(logging.DEBUG)


_logger_validation_warnings = logging.getLogger("cwltool.validation_warnings")
_logger_validation_warnings.setLevel(_logger.getEffectiveLevel())
_logger_validation_warnings.addFilter(LogAsDebugFilter("cwltool.validation_warnings", _logger))

supportedProcessRequirements = ["DockerRequirement",
                                "SchemaDefRequirement",
                                "EnvVarRequirement",
                                "ScatterFeatureRequirement",
                                "SubworkflowFeatureRequirement",
                                "MultipleInputFeatureRequirement",
                                "InlineJavascriptRequirement",
                                "ShellCommandRequirement",
                                "StepInputExpressionRequirement",
                                "ResourceRequirement",
                                "InitialWorkDirRequirement",
                                "TimeLimit",
                                "WorkReuse",
                                "NetworkAccess",
                                "http://commonwl.org/cwltool#TimeLimit",
                                "http://commonwl.org/cwltool#WorkReuse",
                                "http://commonwl.org/cwltool#NetworkAccess",
                                "http://commonwl.org/cwltool#LoadListingRequirement",
                                "http://commonwl.org/cwltool#InplaceUpdateRequirement"]

cwl_files = (
    "Workflow.yml",
    "CommandLineTool.yml",
    "CommonWorkflowLanguage.yml",
    "Process.yml",
    "concepts.md",
    "contrib.md",
    "intro.md",
    "invocation.md")

salad_files = ('metaschema.yml',
               'metaschema_base.yml',
               'salad.md',
               'field_name.yml',
               'import_include.md',
               'link_res.yml',
               'ident_res.yml',
               'vocab_res.yml',
               'vocab_res.yml',
               'field_name_schema.yml',
               'field_name_src.yml',
               'field_name_proc.yml',
               'ident_res_schema.yml',
               'ident_res_src.yml',
               'ident_res_proc.yml',
               'link_res_schema.yml',
               'link_res_src.yml',
               'link_res_proc.yml',
               'vocab_res_schema.yml',
               'vocab_res_src.yml',
               'vocab_res_proc.yml')

SCHEMA_CACHE = {}  # type: Dict[Text, Tuple[Loader, Union[schema.Names, schema.SchemaParseException], Dict[Text, Any], Loader]]
SCHEMA_FILE = None  # type: Optional[Dict[Text, Any]]
SCHEMA_DIR = None  # type: Optional[Dict[Text, Any]]
SCHEMA_ANY = None  # type: Optional[Dict[Text, Any]]

custom_schemas = {}  # type: Dict[Text, Tuple[Text, Text]]

def use_standard_schema(version):
    # type: (Text) -> None
    if version in custom_schemas:
        del custom_schemas[version]
    if version in SCHEMA_CACHE:
        del SCHEMA_CACHE[version]

def use_custom_schema(version, name, text):
    # type: (Text, Text, Union[Text, bytes]) -> None
    if isinstance(text, bytes):
        text2 = text.decode()
    else:
        text2 = text
    custom_schemas[version] = (name, text2)
    if version in SCHEMA_CACHE:
        del SCHEMA_CACHE[version]

def get_schema(version):
    # type: (Text) -> Tuple[Loader, Union[schema.Names, schema.SchemaParseException], Dict[Text,Any], Loader]

    if version in SCHEMA_CACHE:
        return SCHEMA_CACHE[version]

    cache = {}  # type: Dict[Text, Union[bytes, Text]]
    version = version.split("#")[-1]
    if '.dev' in version:
        version = ".".join(version.split(".")[:-1])
    for f in cwl_files:
        try:
            res = resource_stream(__name__, 'schemas/%s/%s' % (version, f))
            cache["https://w3id.org/cwl/" + f] = res.read()
            res.close()
        except IOError:
            pass

    for f in salad_files:
        try:
            res = resource_stream(
                __name__, 'schemas/{}/salad/schema_salad/metaschema/{}'.format(
                    version, f))
            cache["https://w3id.org/cwl/salad/schema_salad/metaschema/"
                  + f] = res.read()
            res.close()
        except IOError:
            pass

    if version in custom_schemas:
        cache[custom_schemas[version][0]] = custom_schemas[version][1]
        SCHEMA_CACHE[version] = schema.load_schema(
            custom_schemas[version][0], cache=cache)
    else:
        SCHEMA_CACHE[version] = schema.load_schema(
            "https://w3id.org/cwl/CommonWorkflowLanguage.yml", cache=cache)

    return SCHEMA_CACHE[version]


def shortname(inputid):
    # type: (Text) -> Text
    d = urllib.parse.urlparse(inputid)
    if d.fragment:
        return d.fragment.split(u"/")[-1]
    return d.path.split(u"/")[-1]


def checkRequirements(rec, supported_process_requirements):
    # type: (Any, Iterable[Any]) -> None
    if isinstance(rec, MutableMapping):
        if "requirements" in rec:
            for i, entry in enumerate(rec["requirements"]):
                with SourceLine(rec["requirements"], i, UnsupportedRequirement):
                    if entry["class"] not in supported_process_requirements:
                        raise UnsupportedRequirement(
                            u"Unsupported requirement {}".format(entry["class"]))
        for key in rec:
            checkRequirements(rec[key], supported_process_requirements)
    if isinstance(rec, MutableSequence):
        for entry in rec:
            checkRequirements(entry, supported_process_requirements)


def stage_files(pathmapper,             # type: PathMapper
                stage_func=None,        # type: Callable[..., Any]
                ignore_writable=False,  # type: bool
                symlink=True,           # type: bool
                secret_store=None       # type: SecretStore
               ):  # type: (...) -> None
    """Link or copy files to their targets. Create them as needed."""
    for key, entry in pathmapper.items():
        if not entry.staged:
            continue
        if not os.path.exists(os.path.dirname(entry.target)):
            os.makedirs(os.path.dirname(entry.target), 0o0755)
        if entry.type in ("File", "Directory") and os.path.exists(entry.resolved):
            if symlink:  # Use symlink func if allowed
                if onWindows():
                    if entry.type == "File":
                        shutil.copy(entry.resolved, entry.target)
                    elif entry.type == "Directory":
                        if os.path.exists(entry.target) \
                                and os.path.isdir(entry.target):
                            shutil.rmtree(entry.target)
                        copytree_with_merge(entry.resolved, entry.target)
                else:
                    os.symlink(entry.resolved, entry.target)
            elif stage_func is not None:
                stage_func(entry.resolved, entry.target)
        elif entry.type == "Directory" and not os.path.exists(entry.target) \
                and entry.resolved.startswith("_:"):
            os.makedirs(entry.target, 0o0755)
        elif entry.type == "WritableFile" and not ignore_writable:
            shutil.copy(entry.resolved, entry.target)
            ensure_writable(entry.target)
        elif entry.type == "WritableDirectory" and not ignore_writable:
            if entry.resolved.startswith("_:"):
                os.makedirs(entry.target, 0o0755)
            else:
                shutil.copytree(entry.resolved, entry.target)
                ensure_writable(entry.target)
        elif entry.type == "CreateFile" or entry.type == "CreateWritableFile":
            with open(entry.target, "wb") as new:
                if secret_store is not None:
                    new.write(
                        secret_store.retrieve(entry.resolved).encode("utf-8"))
                else:
                    new.write(entry.resolved.encode("utf-8"))
            if entry.type == "CreateFile":
                os.chmod(entry.target, stat.S_IRUSR)  # Read only
            else:  # it is a "CreateWritableFile"
                ensure_writable(entry.target)
            pathmapper.update(
                key, entry.target, entry.target, entry.type, entry.staged)


def relocateOutputs(outputObj,             # type: Union[Dict[Text, Any],List[Dict[Text, Any]]]
                    destination_path,      # type: Text
                    source_directories,    # type: Set[Text]
                    action,                # type: Text
                    fs_access,             # type: StdFsAccess
                    compute_checksum=True,  # type: bool
                    path_mapper=PathMapper
                    ):
    # type: (...) -> Union[Dict[Text, Any], List[Dict[Text, Any]]]
    adjustDirObjs(outputObj, functools.partial(get_listing, fs_access, recursive=True))

    if action not in ("move", "copy"):
        return outputObj

    def _collectDirEntries(obj):
        # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]]) -> Iterator[Dict[Text, Any]]
        if isinstance(obj, dict):
            if obj.get("class") in ("File", "Directory"):
                yield obj
            else:
                for sub_obj in obj.values():
                    for dir_entry in _collectDirEntries(sub_obj):
                        yield dir_entry
        elif isinstance(obj, MutableSequence):
            for sub_obj in obj:
                for dir_entry in _collectDirEntries(sub_obj):
                    yield dir_entry

    def _relocate(src, dst):
        if src == dst:
            return

        # If the source is not contained in source_directories we're not allowed to delete it
        src_can_deleted = any(os.path.commonprefix([p, src]) == p for p in source_directories)

        _action = "move" if action == "move" and src_can_deleted else "copy"

        if _action == "move":
            _logger.debug("Moving %s to %s", src, dst)
            if fs_access.isdir(src) and fs_access.isdir(dst):
                # merge directories
                for dir_entry in scandir(src):
                    _relocate(dir_entry.path, fs_access.join(dst, dir_entry.name))
            else:
                shutil.move(src, dst)

        elif _action == "copy":
            _logger.debug("Copying %s to %s", src, dst)
            if fs_access.isdir(src):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                elif os.path.isfile(dst):
                    os.unlink(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    outfiles = list(_collectDirEntries(outputObj))
    pm = path_mapper(outfiles, "", destination_path, separateDirs=False)
    stage_files(pm, stage_func=_relocate, symlink=False)

    def _check_adjust(a_file):
        a_file["location"] = file_uri(pm.mapper(a_file["location"])[1])
        if "contents" in a_file:
            del a_file["contents"]
        return a_file

    visit_class(outputObj, ("File", "Directory"), _check_adjust)

    if compute_checksum:
        visit_class(outputObj, ("File",), functools.partial(
            compute_checksums, fs_access))
    return outputObj


def cleanIntermediate(output_dirs):  # type: (Iterable[Text]) -> None
    for a in output_dirs:
        if os.path.exists(a):
            _logger.debug(u"Removing intermediate output directory %s", a)
            shutil.rmtree(a, True)

def add_sizes(fsaccess, obj):  # type: (StdFsAccess, Dict[Text, Any]) -> None
    if 'location' in obj:
        try:
            if "size" not in obj:
                obj["size"] = fsaccess.size(obj["location"])
        except OSError:
            pass
    elif 'contents' in obj:
        obj["size"] = len(obj['contents'])
    else:
        return  # best effort

def fill_in_defaults(inputs,   # type: List[Dict[Text, Text]]
                     job,      # type: Dict[Text, Union[Dict[Text, Any], List[Any], Text, None]]
                     fsaccess  # type: StdFsAccess
                    ):  # type: (...) -> None
    for e, inp in enumerate(inputs):
        with SourceLine(inputs, e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
            fieldname = shortname(inp[u"id"])
            if job.get(fieldname) is not None:
                pass
            elif job.get(fieldname) is None and u"default" in inp:
                job[fieldname] = copy.deepcopy(inp[u"default"])
            elif job.get(fieldname) is None and u"null" in aslist(inp[u"type"]):
                job[fieldname] = None
            else:
                raise WorkflowException("Missing required input parameter '%s'" % shortname(inp["id"]))


def avroize_type(field_type, name_prefix=""):
    # type: (Union[List[Dict[Text, Any]], Dict[Text, Any]], Text) -> Any
    """
    adds missing information to a type so that CWL types are valid in schema_salad.
    """
    if isinstance(field_type, MutableSequence):
        for field in field_type:
            avroize_type(field, name_prefix)
    elif isinstance(field_type, MutableMapping):
        if field_type["type"] in ("enum", "record"):
            if "name" not in field_type:
                field_type["name"] = name_prefix + Text(uuid.uuid4())
        if field_type["type"] == "record":
            avroize_type(field_type["fields"], name_prefix)
        if field_type["type"] == "array":
            avroize_type(field_type["items"], name_prefix)
        if isinstance(field_type["type"], MutableSequence):
            for ctype in field_type["type"]:
                avroize_type(ctype, name_prefix)
    return field_type

def get_overrides(overrides, toolid):  # type: (List[Dict[Text, Any]], Text) -> Dict[Text, Any]
    req = {}  # type: Dict[Text, Any]
    if not isinstance(overrides, MutableSequence):
        raise validate.ValidationException("Expected overrides to be a list, but was %s" % type(overrides))
    for ov in overrides:
        if ov["overrideTarget"] == toolid:
            req.update(ov)
    return req


_VAR_SPOOL_ERROR = textwrap.dedent(
    """
    Non-portable reference to /var/spool/cwl detected: '{}'.
    To fix, replace /var/spool/cwl with $(runtime.outdir) or add
    DockerRequirement to the 'requirements' section and declare
    'dockerOutputDirectory: /var/spool/cwl'.
    """)


def var_spool_cwl_detector(obj,           # type: Union[MutableMapping, List, Text]
                           item=None,     # type: Optional[Any]
                           obj_key=None,  # type: Optional[Any]
                          ):              # type: (...)->bool
    """ Detects any textual reference to /var/spool/cwl. """
    r = False
    if isinstance(obj, string_types):
        if "var/spool/cwl" in obj and obj_key != "dockerOutputDirectory":
            _logger.warning(
                SourceLine(item=item, key=obj_key, raise_type=Text).makeError(
                    _VAR_SPOOL_ERROR.format(obj)))
            r = True
    elif isinstance(obj, MutableMapping):
        for key, value in iteritems(obj):
            r = var_spool_cwl_detector(value, obj, key) or r
    elif isinstance(obj, MutableSequence):
        for key, value in enumerate(obj):
            r = var_spool_cwl_detector(value, obj, key) or r
    return r

def eval_resource(builder, resource_req):  # type: (Builder, Text) -> Any
    if expression.needs_parsing(resource_req):
        return builder.do_eval(resource_req)
    return resource_req

# Threshold where the "too many files" warning kicks in
FILE_COUNT_WARNING = 5000

class Process(with_metaclass(abc.ABCMeta, HasReqsHints)):
    def __init__(self,
                 toolpath_object,      # type: MutableMapping[Text, Any]
                 loadingContext        # type: LoadingContext
                ):  # type: (...) -> None
        self.metadata = getdefault(loadingContext.metadata, {})  # type: Dict[Text,Any]
        self.provenance_object = None  # type: Optional[ProvenanceProfile]
        self.parent_wf = None          # type: Optional[ProvenanceProfile]
        global SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY  # pylint: disable=global-statement
        if SCHEMA_FILE is None or SCHEMA_ANY is None or SCHEMA_DIR is None:
            get_schema("v1.0")
            SCHEMA_ANY = cast(Dict[Text, Any],
                              SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/salad#Any"])
            SCHEMA_FILE = cast(Dict[Text, Any],
                               SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#File"])
            SCHEMA_DIR = cast(Dict[Text, Any],
                              SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#Directory"])

        self.names = schema.make_avro_schema([SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY],
                                             Loader({}))
        self.tool = toolpath_object
        self.requirements = copy.deepcopy(getdefault(loadingContext.requirements, []))
        self.requirements.extend(self.tool.get("requirements", []))
        self.requirements.extend(get_overrides(getdefault(loadingContext.overrides_list, []),
                                               self.tool["id"]).get("requirements", []))
        self.hints = copy.deepcopy(getdefault(loadingContext.hints, []))
        self.hints.extend(self.tool.get("hints", []))
        # Versions of requirements and hints which aren't mutated.
        self.original_requirements = copy.deepcopy(self.requirements)
        self.original_hints = copy.deepcopy(self.hints)
        self.doc_loader = loadingContext.loader
        self.doc_schema = loadingContext.avsc_names

        self.formatgraph = None  # type: Optional[Graph]
        if self.doc_loader is not None:
            self.formatgraph = self.doc_loader.graph

        checkRequirements(self.tool, supportedProcessRequirements)
        self.validate_hints(loadingContext.avsc_names, self.tool.get("hints", []),
                            strict=getdefault(loadingContext.strict, False))

        self.schemaDefs = {}  # type: Dict[Text,Dict[Text, Any]]

        sd, _ = self.get_requirement("SchemaDefRequirement")

        if sd is not None:
            sdtypes = avroize_type(sd["types"])
            av = schema.make_valid_avro(sdtypes, {t["name"]: t for t in sdtypes}, set())
            for i in av:
                self.schemaDefs[i["name"]] = i  # type: ignore
            schema.make_avsc_object(schema.convert_to_dict(av), self.names)

        # Build record schema from inputs
        self.inputs_record_schema = {
            "name": "input_record_schema", "type": "record",
            "fields": []}  # type: Dict[Text, Any]
        self.outputs_record_schema = {
            "name": "outputs_record_schema", "type": "record",
            "fields": []}  # type: Dict[Text, Any]

        for key in ("inputs", "outputs"):
            for i in self.tool[key]:
                c = copy.deepcopy(i)
                c["name"] = shortname(c["id"])
                del c["id"]

                if "type" not in c:
                    raise validate.ValidationException(
                        u"Missing 'type' in parameter '{}'".format(c["name"]))

                if "default" in c and "null" not in aslist(c["type"]):
                    nullable = ["null"]
                    nullable.extend(aslist(c["type"]))
                    c["type"] = nullable
                else:
                    c["type"] = c["type"]
                c["type"] = avroize_type(c["type"], c["name"])
                if key == "inputs":
                    self.inputs_record_schema["fields"].append(c)
                elif key == "outputs":
                    self.outputs_record_schema["fields"].append(c)

        with SourceLine(toolpath_object, "inputs", validate.ValidationException):
            self.inputs_record_schema = cast(
                Dict[Text, Any], schema.make_valid_avro(
                    self.inputs_record_schema, {}, set()))
            schema.make_avsc_object(
                schema.convert_to_dict(self.inputs_record_schema), self.names)
        with SourceLine(toolpath_object, "outputs", validate.ValidationException):
            self.outputs_record_schema = cast(
                Dict[Text, Any],
                schema.make_valid_avro(self.outputs_record_schema, {}, set()))
            schema.make_avsc_object(
                schema.convert_to_dict(self.outputs_record_schema), self.names)

        if toolpath_object.get("class") is not None \
                and not getdefault(loadingContext.disable_js_validation, False):
            if loadingContext.js_hint_options_file is not None:
                try:
                    with open(loadingContext.js_hint_options_file) as options_file:
                        validate_js_options = json.load(options_file)
                except (OSError, ValueError) as err:
                    _logger.error(
                        "Failed to read options file %s",
                        loadingContext.js_hint_options_file)
                    raise err
            else:
                validate_js_options = None
            if self.doc_schema is not None:
                validate_js_expressions(
                    cast(CommentedMap, toolpath_object),
                    self.doc_schema.names[toolpath_object["class"]],
                    validate_js_options)

        dockerReq, is_req = self.get_requirement("DockerRequirement")

        if dockerReq is not None and "dockerOutputDirectory" in dockerReq\
                and is_req is not None and not is_req:
            _logger.warning(SourceLine(
                item=dockerReq, raise_type=Text).makeError(
                    "When 'dockerOutputDirectory' is declared, DockerRequirement "
                    "should go in the 'requirements' section, not 'hints'."""))

        if dockerReq is not None and is_req is not None\
                and dockerReq.get("dockerOutputDirectory") == "/var/spool/cwl":
            if is_req:
                # In this specific case, it is legal to have /var/spool/cwl, so skip the check.
                pass
            else:
                # Must be a requirement
                var_spool_cwl_detector(self.tool)
        else:
            var_spool_cwl_detector(self.tool)

    def _init_job(self, joborder, runtime_context):
        # type: (Mapping[Text, Text], RuntimeContext) -> Builder

        job = cast(Dict[Text, Union[Dict[Text, Any], List[Any], Text, None]],
                   copy.deepcopy(joborder))

        make_fs_access = getdefault(runtime_context.make_fs_access, StdFsAccess)
        fs_access = make_fs_access(runtime_context.basedir)

        load_listing_req, _ = self.get_requirement(
            "http://commonwl.org/cwltool#LoadListingRequirement")
        if load_listing_req is not None:
            load_listing = load_listing_req.get("loadListing")
        else:
            load_listing = "deep_listing"   # will default to "no_listing" in CWL v1.1

        # Validate job order
        try:
            fill_in_defaults(self.tool[u"inputs"], job, fs_access)

            normalizeFilesDirs(job)
            schema = self.names.get_name("input_record_schema", "")
            if schema is None:
                raise WorkflowException("Missing input record schema: "
                    "{}".format(self.names))
            validate.validate_ex(schema, job, strict=False,
                                 logger=_logger_validation_warnings)

            if load_listing and load_listing != "no_listing":
                get_listing(fs_access, job, recursive=(load_listing == "deep_listing"))

            visit_class(job, ("File",), functools.partial(add_sizes, fs_access))

            if load_listing == "deep_listing" and load_listing_req is None:
                for i, inparm in enumerate(self.tool["inputs"]):
                    k = shortname(inparm["id"])
                    if k not in job:
                        continue
                    v = job[k]
                    dircount = [0]
                    def inc(d):  # type: (List[int]) -> None
                        d[0] += 1
                    visit_class(v, ("Directory",), lambda x: inc(dircount))
                    if dircount[0] == 0:
                        continue
                    filecount = [0]
                    visit_class(v, ("File",), lambda x: inc(filecount))
                    if filecount[0] > FILE_COUNT_WARNING:
                        # Long lines in this message are okay, will be reflowed based on terminal columns.
                        _logger.warning(strip_dup_lineno(SourceLine(self.tool["inputs"], i, Text).makeError(
                    """Recursive directory listing has resulted in a large number of File objects (%s) passed to the input parameter '%s'.  This may negatively affect workflow performance and memory use.

If this is a problem, use the hint 'cwltool:LoadListingRequirement' with "shallow_listing" or "no_listing" to change the directory listing behavior:

$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
hints:
  cwltool:LoadListingRequirement:
    loadListing: shallow_listing

""" % (filecount[0], k))))

        except (validate.ValidationException, WorkflowException) as err:
            raise WorkflowException("Invalid job input record:\n" + Text(err))

        files = []  # type: List[Dict[Text, Text]]
        bindings = CommentedSeq()
        tmpdir = u""
        stagedir = u""

        docker_req, _ = self.get_requirement("DockerRequirement")
        default_docker = None

        if docker_req is None and runtime_context.default_container:
            default_docker = runtime_context.default_container

        if (docker_req or default_docker) and runtime_context.use_container:
            if docker_req is not None:
                # Check if docker output directory is absolute
                if docker_req.get("dockerOutputDirectory") and \
                        docker_req.get("dockerOutputDirectory").startswith('/'):
                    outdir = docker_req.get("dockerOutputDirectory")
                else:
                    outdir = docker_req.get("dockerOutputDirectory") or \
                        runtime_context.docker_outdir or random_outdir()
            elif default_docker is not None:
                outdir = runtime_context.docker_outdir or random_outdir()
            tmpdir = runtime_context.docker_tmpdir or "/tmp"
            stagedir = runtime_context.docker_stagedir or "/var/lib/cwl"
        else:
            outdir = fs_access.realpath(
                runtime_context.outdir or tempfile.mkdtemp(
                    prefix=getdefault(runtime_context.tmp_outdir_prefix,
                                      DEFAULT_TMP_PREFIX)))
            if self.tool[u"class"] != 'Workflow':
                tmpdir = fs_access.realpath(runtime_context.tmpdir
                                            or tempfile.mkdtemp())
                stagedir = fs_access.realpath(runtime_context.stagedir
                                              or tempfile.mkdtemp())

        builder = Builder(job,
                          files,
                          bindings,
                          self.schemaDefs,
                          self.names,
                          self.requirements,
                          self.hints,
                          {},
                          runtime_context.mutation_manager,
                          self.formatgraph,
                          make_fs_access,
                          fs_access,
                          runtime_context.job_script_provider,
                          runtime_context.eval_timeout,
                          runtime_context.debug,
                          runtime_context.js_console,
                          runtime_context.force_docker_pull,
                          load_listing,
                          outdir,
                          tmpdir,
                          stagedir)

        bindings.extend(builder.bind_input(
            self.inputs_record_schema, job,
            discover_secondaryFiles=getdefault(runtime_context.toplevel, False)))

        if self.tool.get("baseCommand"):
            for index, command in enumerate(aslist(self.tool["baseCommand"])):
                bindings.append({
                    "position": [-1000000, index],
                    "datum": command
                })

        if self.tool.get("arguments"):
            for i, arg in enumerate(self.tool["arguments"]):
                lc = self.tool["arguments"].lc.data[i]
                filename = self.tool["arguments"].lc.filename
                bindings.lc.add_kv_line_col(len(bindings), lc)
                if isinstance(arg, MutableMapping):
                    arg = copy.deepcopy(arg)
                    if arg.get("position"):
                        arg["position"] = [arg["position"], i]
                    else:
                        arg["position"] = [0, i]
                    bindings.append(arg)
                elif ("$(" in arg) or ("${" in arg):
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("valueFrom", arg)
                    ))
                    cm.lc.add_kv_line_col("valueFrom", lc)
                    cm.lc.filename = filename
                    bindings.append(cm)
                else:
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("datum", arg)
                    ))
                    cm.lc.add_kv_line_col("datum", lc)
                    cm.lc.filename = filename
                    bindings.append(cm)

        # use python2 like sorting of heterogeneous lists
        # (containing str and int types),
        if PY3:
            key = functools.cmp_to_key(cmp_like_py2)
        else:  # PY2
            key = lambda d: d["position"]

        # This awkward construction replaces the contents of
        # "bindings" in place (because Builder expects it to be
        # mutated in place, sigh, I'm sorry) with its contents sorted,
        # supporting different versions of Python and ruamel.yaml with
        # different behaviors/bugs in CommentedSeq.
        bindings_copy = copy.deepcopy(bindings)
        del bindings[:]
        bindings.extend(sorted(bindings_copy, key=key))

        if self.tool[u"class"] != 'Workflow':
            builder.resources = self.evalResources(builder, runtime_context)
        return builder

    def evalResources(self, builder, runtimeContext):
        # type: (Builder, RuntimeContext) -> Dict[str, int]
        resourceReq, _ = self.get_requirement("ResourceRequirement")
        if resourceReq is None:
            resourceReq = {}
        request = {
            "coresMin": 1,
            "coresMax": 1,
            "ramMin": 1024,
            "ramMax": 1024,
            "tmpdirMin": 1024,
            "tmpdirMax": 1024,
            "outdirMin": 1024,
            "outdirMax": 1024
        }  # type: Dict[str, int]
        for a in ("cores", "ram", "tmpdir", "outdir"):
            mn = None
            mx = None
            if resourceReq.get(a + "Min"):
                mn = eval_resource(builder, resourceReq[a + "Min"])
            if resourceReq.get(a + "Max"):
                mx = eval_resource(builder, resourceReq[a + "Max"])
            if mn is None:
                mn = mx
            elif mx is None:
                mx = mn

            if mn is not None:
                request[a + "Min"] = cast(int, mn)
                request[a + "Max"] = cast(int, mx)

        if runtimeContext.select_resources is not None:
            return runtimeContext.select_resources(request, runtimeContext)
        return {
            "cores": request["coresMin"],
            "ram": request["ramMin"],
            "tmpdirSize": request["tmpdirMin"],
            "outdirSize": request["outdirMin"],
        }

    def validate_hints(self, avsc_names, hints, strict):
        # type: (Any, List[Dict[Text, Any]], bool) -> None
        for i, r in enumerate(hints):
            sl = SourceLine(hints, i, validate.ValidationException)
            with sl:
                if avsc_names.get_name(r["class"], "") is not None and self.doc_loader is not None:
                    plain_hint = dict((key, r[key]) for key in r if key not in
                                      self.doc_loader.identifiers)  # strip identifiers
                    validate.validate_ex(
                        avsc_names.get_name(plain_hint["class"], ""),
                        plain_hint, strict=strict)
                else:
                    _logger.info(sl.makeError(u"Unknown hint %s" % (r["class"])))

    def visit(self, op):  # type: (Callable[[MutableMapping[Text, Any]], None]) -> None
        op(self.tool)

    @abc.abstractmethod
    def job(self,
            job_order,         # type: Mapping[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            runtimeContext     # type: RuntimeContext
           ):  # type: (...) -> Generator[Any, None, None]
        # FIXME: Declare base type for what Generator yields
        pass


_names = set()  # type: Set[Text]


def uniquename(stem, names=None):  # type: (Text, Set[Text]) -> Text
    global _names
    if names is None:
        names = _names
    c = 1
    u = stem
    while u in names:
        c += 1
        u = u"%s_%s" % (stem, c)
    names.add(u)
    return u


def nestdir(base, deps):
    # type: (Text, Dict[Text, Any]) -> Dict[Text, Any]
    dirname = os.path.dirname(base) + "/"
    subid = deps["location"]
    if subid.startswith(dirname):
        s2 = subid[len(dirname):]
        sp = s2.split('/')
        sp.pop()
        while sp:
            nx = sp.pop()
            deps = {
                "class": "Directory",
                "basename": nx,
                "listing": [deps]
            }
    return deps


def mergedirs(listing):
    # type: (List[Dict[Text, Any]]) -> List[Dict[Text, Any]]
    r = []  # type: List[Dict[Text, Any]]
    ents = {}  # type: Dict[Text, Any]
    collided = set()  # type: Set[Text]
    for e in listing:
        if e["basename"] not in ents:
            ents[e["basename"]] = e
        elif e["class"] == "Directory":
            if e.get("listing"):
                ents[e["basename"]].setdefault("listing", []).extend(e["listing"])
            if ents[e["basename"]]["location"].startswith("_:"):
                ents[e["basename"]]["location"] = e["location"]
        elif e["location"] != ents[e["basename"]]["location"]:
            # same basename, different location, collision,
            # rename both.
            collided.add(e["basename"])
            e2 = ents[e["basename"]]

            e["basename"] = urllib.parse.quote(e["location"], safe="")
            e2["basename"] = urllib.parse.quote(e2["location"], safe="")

            e["nameroot"], e["nameext"] = os.path.splitext(e["basename"])
            e2["nameroot"], e2["nameext"] = os.path.splitext(e2["basename"])

            ents[e["basename"]] = e
            ents[e2["basename"]] = e2
    for c in collided:
        del ents[c]
    for e in itervalues(ents):
        if e["class"] == "Directory" and "listing" in e:
            e["listing"] = mergedirs(e["listing"])
    r.extend(itervalues(ents))
    return r


CWL_IANA = "https://www.iana.org/assignments/media-types/application/cwl"

def scandeps(base,                          # type: Text
             doc,                           # type: Any
             reffields,                     # type: Set[Text]
             urlfields,                     # type: Set[Text]
             loadref,                       # type: Callable[[Text, Text], Text]
             urljoin=urllib.parse.urljoin,  # type: Callable[[Text, Text], Text]
             nestdirs=True                  # type: bool
            ):  # type: (...) -> List[Dict[Text, Text]]
    r = []  # type: List[Dict[Text, Text]]
    if isinstance(doc, MutableMapping):
        if "id" in doc:
            if doc["id"].startswith("file://"):
                df, _ = urllib.parse.urldefrag(doc["id"])
                if base != df:
                    r.append({
                        "class": "File",
                        "location": df,
                        "format": CWL_IANA
                    })
                    base = df

        if doc.get("class") in ("File", "Directory") and "location" in urlfields:
            u = doc.get("location", doc.get("path"))
            if u and not u.startswith("_:"):
                deps = {"class": doc["class"],
                        "location": urljoin(base, u)
                       }  # type: Dict[Text, Any]
                if "basename" in doc:
                    deps["basename"] = doc["basename"]
                if doc["class"] == "Directory" and "listing" in doc:
                    deps["listing"] = doc["listing"]
                if doc["class"] == "File" and "secondaryFiles" in doc:
                    deps["secondaryFiles"] = doc["secondaryFiles"]
                if nestdirs:
                    deps = nestdir(base, deps)
                r.append(deps)
            else:
                if doc["class"] == "Directory" and "listing" in doc:
                    r.extend(scandeps(
                        base, doc["listing"], reffields, urlfields, loadref,
                        urljoin=urljoin, nestdirs=nestdirs))
                elif doc["class"] == "File" and "secondaryFiles" in doc:
                    r.extend(scandeps(
                        base, doc["secondaryFiles"], reffields, urlfields,
                        loadref, urljoin=urljoin, nestdirs=nestdirs))

        for k, v in iteritems(doc):
            if k in reffields:
                for u in aslist(v):
                    if isinstance(u, MutableMapping):
                        r.extend(scandeps(
                            base, u, reffields, urlfields, loadref,
                            urljoin=urljoin, nestdirs=nestdirs))
                    else:
                        sub = loadref(base, u)
                        subid = urljoin(base, u)
                        deps = {
                            "class": "File",
                            "location": subid,
                            "format": CWL_IANA
                        }
                        sf = scandeps(
                            subid, sub, reffields, urlfields, loadref,
                            urljoin=urljoin, nestdirs=nestdirs)
                        if sf:
                            deps["secondaryFiles"] = sf
                        if nestdirs:
                            deps = nestdir(base, deps)
                        r.append(deps)
            elif k in urlfields and k != "location":
                for u in aslist(v):
                    deps = {
                        "class": "File",
                        "location": urljoin(base, u)
                    }
                    if nestdirs:
                        deps = nestdir(base, deps)
                    r.append(deps)
            elif k not in ("listing", "secondaryFiles"):
                r.extend(scandeps(
                    base, v, reffields, urlfields, loadref, urljoin=urljoin,
                    nestdirs=nestdirs))
    elif isinstance(doc, MutableSequence):
        for d in doc:
            r.extend(scandeps(
                base, d, reffields, urlfields, loadref, urljoin=urljoin,
                nestdirs=nestdirs))

    if r:
        normalizeFilesDirs(r)
        r = mergedirs(r)

    return r


def compute_checksums(fs_access, fileobj):
    if "checksum" not in fileobj:
        checksum = hashlib.sha1()
        with fs_access.open(fileobj["location"], "rb") as f:
            contents = f.read(1024 * 1024)
            while contents != b"":
                checksum.update(contents)
                contents = f.read(1024 * 1024)
        fileobj["checksum"] = "sha1$%s" % checksum.hexdigest()
        fileobj["size"] = fs_access.size(fileobj["location"])
