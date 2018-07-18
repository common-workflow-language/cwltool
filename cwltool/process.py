from __future__ import absolute_import

import abc
import copy
import errno
import functools
from functools import cmp_to_key
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
from typing import (Any, Callable, Dict,  # pylint: disable=unused-import
                    Generator, List, Optional, Set, Text, Tuple, Union, cast,
                    TYPE_CHECKING)

from pkg_resources import resource_stream
from rdflib import Graph  # pylint: disable=unused-import
from ruamel.yaml.comments import CommentedMap, CommentedSeq
import schema_salad.schema as schema
import schema_salad.validate as validate
from schema_salad.ref_resolver import Loader, file_uri
from schema_salad.sourceline import SourceLine
import six
from six import iteritems, itervalues, string_types
from six.moves import urllib

from . import expression
from .builder import Builder, HasReqsHints
from .errors import UnsupportedRequirement, WorkflowException
from .mutation import MutationManager  # pylint: disable=unused-import
from .pathmapper import (PathMapper, adjustDirObjs, ensure_writable,
                         get_listing, normalizeFilesDirs, visit_class)
from .secrets import SecretStore  # pylint: disable=unused-import
from .software_requirements import (  # pylint: disable=unused-import
    DependenciesConfiguration)
from .stdfsaccess import StdFsAccess
from .utils import (DEFAULT_TMP_PREFIX, add_sizes, aslist, cmp_like_py2,
                    copytree_with_merge, onWindows)
from .validate_js import validate_js_expressions
from .context import LoadingContext, RuntimeContext, getdefault
if TYPE_CHECKING:
    from .provenance import CreateProvProfile  # pylint: disable=unused-import


class LogAsDebugFilter(logging.Filter):
    def __init__(self, name, parent):  # type: (Text, logging.Logger) -> None
        name = str(name)
        super(LogAsDebugFilter, self).__init__(name)
        self.parent = parent

    def filter(self, record):
        return self.parent.isEnabledFor(logging.DEBUG)


_logger = logging.getLogger("cwltool")
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
                __name__, 'schemas/%s/salad/schema_salad/metaschema/%s'
                          % (version, f))
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
    else:
        return d.path.split(u"/")[-1]


def checkRequirements(rec, supportedProcessRequirements):
    # type: (Any, Iterable[Any]) -> None
    if isinstance(rec, dict):
        if "requirements" in rec:
            for i, r in enumerate(rec["requirements"]):
                with SourceLine(rec["requirements"], i, UnsupportedRequirement):
                    if r["class"] not in supportedProcessRequirements:
                        raise UnsupportedRequirement(u"Unsupported requirement %s" % r["class"])
        for d in rec:
            checkRequirements(rec[d], supportedProcessRequirements)
    if isinstance(rec, list):
        for d in rec:
            checkRequirements(d, supportedProcessRequirements)


def adjustFilesWithSecondary(rec, op, primary=None):
    """Apply a mapping function to each File path in the object `rec`, propagating
    the primary file associated with a group of secondary files.
    """

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"], primary=primary)
            adjustFilesWithSecondary(rec.get("secondaryFiles", []), op,
                                     primary if primary else rec["path"])
        else:
            for d in rec:
                adjustFilesWithSecondary(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFilesWithSecondary(d, op, primary)


def stageFiles(pm, stageFunc=None, ignoreWritable=False, symLink=True, secret_store=None):
    # type: (PathMapper, Callable[..., Any], bool, bool, SecretStore) -> None
    for f, p in pm.items():
        if not p.staged:
            continue
        if not os.path.exists(os.path.dirname(p.target)):
            os.makedirs(os.path.dirname(p.target), 0o0755)
        if p.type in ("File", "Directory") and (os.path.exists(p.resolved)):
            if symLink:  # Use symlink func if allowed
                if onWindows():
                    if p.type == "File":
                        shutil.copy(p.resolved, p.target)
                    elif p.type == "Directory":
                        if os.path.exists(p.target) and os.path.isdir(p.target):
                            shutil.rmtree(p.target)
                        copytree_with_merge(p.resolved, p.target)
                else:
                    os.symlink(p.resolved, p.target)
            elif stageFunc is not None:
                stageFunc(p.resolved, p.target)
        elif p.type == "Directory" and not os.path.exists(p.target) and p.resolved.startswith("_:"):
            os.makedirs(p.target, 0o0755)
        elif p.type == "WritableFile" and not ignoreWritable:
            shutil.copy(p.resolved, p.target)
            ensure_writable(p.target)
        elif p.type == "WritableDirectory" and not ignoreWritable:
            if p.resolved.startswith("_:"):
                os.makedirs(p.target, 0o0755)
            else:
                shutil.copytree(p.resolved, p.target)
                ensure_writable(p.target)
        elif p.type == "CreateFile":
            with open(p.target, "wb") as n:
                if secret_store:
                    n.write(secret_store.retrieve(p.resolved).encode("utf-8"))
                else:
                    n.write(p.resolved.encode("utf-8"))
            ensure_writable(p.target)

def collectFilesAndDirs(obj, out):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]], List[Dict[Text, Any]]) -> None
    if isinstance(obj, dict):
        if obj.get("class") in ("File", "Directory"):
            out.append(obj)
        else:
            for v in obj.values():
                collectFilesAndDirs(v, out)
    if isinstance(obj, list):
        for l in obj:
            collectFilesAndDirs(l, out)


def relocateOutputs(outputObj,             # type: Union[Dict[Text, Any],List[Dict[Text, Any]]]
                    outdir,                # type: Text
                    output_dirs,           # type: Set[Text]
                    action,                # type: Text
                    fs_access,             # type: StdFsAccess
                    compute_checksum=True  # type: bool
                    ):
    # type: (...) -> Union[Dict[Text, Any], List[Dict[Text, Any]]]
    adjustDirObjs(outputObj, functools.partial(get_listing, fs_access, recursive=True))

    if action not in ("move", "copy"):
        return outputObj

    def moveIt(src, dst):
        if action == "move":
            for a in output_dirs:
                if src.startswith(a+"/"):
                    _logger.debug("Moving %s to %s", src, dst)
                    if os.path.isdir(src) and os.path.isdir(dst):
                        # merge directories
                        for root, dirs, files in os.walk(src):
                            for f in dirs+files:
                                moveIt(os.path.join(root, f), os.path.join(dst, f))
                    else:
                        shutil.move(src, dst)
                    return
        if src != dst:
            _logger.debug("Copying %s to %s", src, dst)
            if os.path.isdir(src):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                elif os.path.isfile(dst):
                    os.unlink(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    outfiles = []  # type: List[Dict[Text, Any]]
    collectFilesAndDirs(outputObj, outfiles)
    pm = PathMapper(outfiles, "", outdir, separateDirs=False)
    stageFiles(pm, stageFunc=moveIt, symLink=False)

    def _check_adjust(f):
        f["location"] = file_uri(pm.mapper(f["location"])[1])
        if "contents" in f:
            del f["contents"]
        return f

    visit_class(outputObj, ("File", "Directory"), _check_adjust)
    if compute_checksum:
        visit_class(outputObj, ("File",), functools.partial(compute_checksums, fs_access))

    # If there are symlinks to intermediate output directories, we want to move
    # the real files into the final output location.  If a file is linked more than once,
    # make an internal relative symlink.
    if action == "move":
        relinked = {}  # type: Dict[Text, Text]
        for root, dirs, files in os.walk(outdir):
            for f in dirs+files:
                path = os.path.join(root, f)
                rp = os.path.realpath(path)
                if path != rp:
                    if rp in relinked:
                        if onWindows():
                            if os.path.isfile(path):
                                shutil.copy(os.path.relpath(relinked[rp], path), path)
                            elif os.path.exists(path) and os.path.isdir(path):
                                shutil.rmtree(path)
                                copytree_with_merge(os.path.relpath(relinked[rp], path), path)
                        else:
                            os.unlink(path)
                            os.symlink(os.path.relpath(relinked[rp], path), path)
                    else:
                        for od in output_dirs:
                            if rp.startswith(od+"/"):
                                os.unlink(path)
                                os.rename(rp, path)
                                relinked[rp] = path
                                break

    return outputObj


def cleanIntermediate(output_dirs):  # type: (Set[Text]) -> None
    for a in output_dirs:
        if os.path.exists(a) and empty_subtree(a):
            _logger.debug(u"Removing intermediate output directory %s", a)
            shutil.rmtree(a, True)


def fillInDefaults(inputs,  # type: List[Dict[Text, Text]]
                   job      # Dict[Text, Union[Dict[Text, Any], Any, None]]
                  ):  # type: (...) -> None
    for e, inp in enumerate(inputs):
        with SourceLine(inputs, e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
            fieldname = shortname(inp[u"id"])
            if job.get(fieldname) is not None:
                pass
            elif job.get(fieldname) is None and u"default" in inp:
                job[fieldname] = copy.copy(inp[u"default"])
            elif job.get(fieldname) is None and u"null" in aslist(inp[u"type"]):
                job[fieldname] = None
            else:
                raise WorkflowException("Missing required input parameter '%s'" % shortname(inp["id"]))
    add_sizes(job)


def avroize_type(field_type, name_prefix=""):
    # type: (Union[List[Dict[Text, Any]], Dict[Text, Any]], Text) -> Any
    """
    adds missing information to a type so that CWL types are valid in schema_salad.
    """
    if isinstance(field_type, list):
        for f in field_type:
            avroize_type(f, name_prefix)
    elif isinstance(field_type, dict):
        if field_type["type"] in ("enum", "record"):
            if "name" not in field_type:
                field_type["name"] = name_prefix + Text(uuid.uuid4())
        if field_type["type"] == "record":
            avroize_type(field_type["fields"], name_prefix)
        if field_type["type"] == "array":
            avroize_type(field_type["items"], name_prefix)
    return field_type

def get_overrides(overrides, toolid):  # type: (List[Dict[Text, Any]], Text) -> Dict[Text, Any]
    req = {}  # type: Dict[Text, Any]
    if not isinstance(overrides, list):
        raise validate.ValidationException("Expected overrides to be a list, but was %s" % type(overrides))
    for ov in overrides:
        if ov["overrideTarget"] == toolid:
            req.update(ov)
    return req


_VAR_SPOOL_ERROR=textwrap.dedent(
    """
    Non-portable reference to /var/spool/cwl detected: '{}'.
    To fix, replace /var/spool/cwl with $(runtime.outdir) or add
    DockerRequirement to the 'requirements' section and declare
    'dockerOutputDirectory: /var/spool/cwl'.
    """)


def var_spool_cwl_detector(obj,           # type: Union[Dict, List, Text]
                           item=None,     # type: Optional[Any]
                           obj_key=None,  # type: Optional[Any]
                          ):              # type: (...)->bool
    """ Detects any textual reference to /var/spool/cwl. """
    r = False
    if isinstance(obj, string_types):
        if "var/spool/cwl" in obj and obj_key != "dockerOutputDirectory":
            _logger.warn(
                SourceLine(item=item, key=obj_key, raise_type=Text).makeError(
                    _VAR_SPOOL_ERROR.format(obj)))
            r = True
    elif isinstance(obj, dict):
        for key, value in iteritems(obj):
            r = var_spool_cwl_detector(value, obj, key) or r
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            r = var_spool_cwl_detector(value, obj, key) or r
    return r

def eval_resource(builder, resource_req):  # type: (Builder, Text) -> Any
        if expression.needs_parsing(resource_req):
            visit_class(builder.job, ("File",), add_sizes)
            return builder.do_eval(resource_req)
        return resource_req


class Process(six.with_metaclass(abc.ABCMeta, HasReqsHints)):
    def __init__(self,
                 toolpath_object,      # type: Dict[Text, Any]
                 loadingContext        # type: LoadingContext
                ):  # type: (...) -> None
        self.metadata = getdefault(loadingContext.metadata, {})  # type: Dict[Text,Any]
        self.provenance_object = None  # type: Optional[CreateProvProfile]
        self.parent_wf = None          # type: Optional[CreateProvProfile]
        global SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY  # pylint: disable=global-statement
        if SCHEMA_FILE is None or SCHEMA_ANY is None or SCHEMA_DIR is None:
            get_schema("v1.0")
            SCHEMA_ANY = cast(Dict[Text, Any],
                              SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/salad#Any"])
            SCHEMA_FILE = cast(Dict[Text, Any],
                               SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#File"])
            SCHEMA_DIR = cast(Dict[Text, Any],
                              SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#Directory"])

        names = schema.make_avro_schema([SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY],
                                        Loader({}))[0]
        if isinstance(names, schema.SchemaParseException):
            raise names
        else:
            self.names = names
        self.tool = toolpath_object
        self.requirements = (getdefault(loadingContext.requirements, []) +
                             self.tool.get("requirements", []) +
                             get_overrides(getdefault(loadingContext.overrides_list, []),
                                           self.tool["id"]).get("requirements", []))
        self.hints = getdefault(loadingContext.hints, []) + self.tool.get("hints", [])
        # Versions of requirements and hints which aren't mutated.
        self.original_requirements = copy.deepcopy(self.requirements)
        self.original_hints = copy.deepcopy(self.hints)
        self.doc_loader = loadingContext.loader
        self.doc_schema = loadingContext.avsc_names

        self.formatgraph = None  # type: Optional[Graph]
        if self.doc_loader:
            self.formatgraph = self.doc_loader.graph

        checkRequirements(self.tool, supportedProcessRequirements)
        self.validate_hints(loadingContext.avsc_names, self.tool.get("hints", []),
                            strict=getdefault(loadingContext.strict, False))

        self.schemaDefs = {}  # type: Dict[Text,Dict[Text, Any]]

        sd, _ = self.get_requirement("SchemaDefRequirement")

        if sd:
            sdtypes = sd["types"]
            av = schema.make_valid_avro(sdtypes, {t["name"]: t for t in avroize_type(sdtypes)}, set())
            for i in av:
                self.schemaDefs[i["name"]] = i  # type: ignore
            schema.AvroSchemaFromJSONData(av, self.names)  # type: ignore

        # Build record schema from inputs
        self.inputs_record_schema = {
            "name": "input_record_schema", "type": "record",
            "fields": []}  # type: Dict[Text, Any]
        self.outputs_record_schema = {
            "name": "outputs_record_schema", "type": "record",
            "fields": []}  # type: Dict[Text, Any]

        for key in ("inputs", "outputs"):
            for i in self.tool[key]:
                c = copy.copy(i)
                c["name"] = shortname(c["id"])
                del c["id"]

                if "type" not in c:
                    raise validate.ValidationException(u"Missing 'type' in "
                            "parameter '%s'" % c["name"])

                if "default" in c and "null" not in aslist(c["type"]):
                    c["type"] = ["null"] + aslist(c["type"])
                else:
                    c["type"] = c["type"]
                c["type"] = avroize_type(c["type"], c["name"])
                if key == "inputs":
                    self.inputs_record_schema["fields"].append(c)
                elif key == "outputs":
                    self.outputs_record_schema["fields"].append(c)

        with SourceLine(toolpath_object, "inputs", validate.ValidationException):
            self.inputs_record_schema = cast(
                Dict[six.text_type, Any], schema.make_valid_avro(
                    self.inputs_record_schema, {}, set()))
            schema.AvroSchemaFromJSONData(self.inputs_record_schema, self.names)
        with SourceLine(toolpath_object, "outputs", validate.ValidationException):
            self.outputs_record_schema = cast(Dict[six.text_type, Any],
                    schema.make_valid_avro(self.outputs_record_schema, {}, set()))
            schema.AvroSchemaFromJSONData(self.outputs_record_schema, self.names)

        if toolpath_object.get("class") is not None and not getdefault(loadingContext.disable_js_validation, False):
            if loadingContext.js_hint_options_file is not None:
                try:
                    with open(loadingContext.js_hint_options_file) as options_file:
                        validate_js_options = json.load(options_file)
                except (OSError, ValueError) as e:
                    _logger.error("Failed to read options file %s" % loadingContext.js_hint_options_file)
                    raise e
            else:
                validate_js_options = None
            if self.doc_schema is not None:
                validate_js_expressions(cast(CommentedMap, toolpath_object), self.doc_schema.names[toolpath_object["class"]], validate_js_options)

        dockerReq, is_req = self.get_requirement("DockerRequirement")

        if dockerReq and dockerReq.get("dockerOutputDirectory") and not is_req:
            _logger.warn(SourceLine(
                item=dockerReq, raise_type=Text).makeError(
                "When 'dockerOutputDirectory' is declared, DockerRequirement "
                "should go in the 'requirements' section, not 'hints'."""))

        if dockerReq and dockerReq.get("dockerOutputDirectory") == "/var/spool/cwl":
            if is_req:
                # In this specific case, it is legal to have /var/spool/cwl, so skip the check.
                pass
            else:
                # Must be a requirement
                var_spool_cwl_detector(self.tool)
        else:
            var_spool_cwl_detector(self.tool)

    def _init_job(self, joborder, runtimeContext):
        # type: (Dict[Text, Text], RuntimeContext) -> Builder

        job = cast(Dict[Text, Union[Dict[Text, Any], List,
                                    Text]], copy.deepcopy(joborder))
        # Validate job order
        try:
            fillInDefaults(self.tool[u"inputs"], job)
            normalizeFilesDirs(job)
            validate.validate_ex(self.names.get_name("input_record_schema", ""),
                                 job, strict=False, logger=_logger_validation_warnings)
        except (validate.ValidationException, WorkflowException) as e:
            raise WorkflowException("Invalid job input record:\n" + Text(e))

        files = []  # type: List[Dict[Text, Text]]
        bindings = CommentedSeq()
        make_fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)
        fs_access = make_fs_access(runtimeContext.basedir)
        tmpdir = u""
        stagedir = u""

        loadListingReq, _ = self.get_requirement("http://commonwl.org/cwltool#LoadListingRequirement")
        if loadListingReq:
            loadListing = loadListingReq.get("loadListing")
        else:
            loadListing = "deep_listing"   # will default to "no_listing" in CWL v1.1

        dockerReq, _ = self.get_requirement("DockerRequirement")
        defaultDocker = None

        if dockerReq is None and runtimeContext.default_container:
            defaultDocker = runtimeContext.default_container

        if (dockerReq or defaultDocker) and runtimeContext.use_container:
            if dockerReq:
                # Check if docker output directory is absolute
                if dockerReq.get("dockerOutputDirectory") and \
                        dockerReq.get("dockerOutputDirectory").startswith('/'):
                    outdir = dockerReq.get("dockerOutputDirectory")
                else:
                    outdir = dockerReq.get("dockerOutputDirectory") or \
                        runtimeContext.docker_outdir or "/var/spool/cwl"
            elif defaultDocker:
                outdir = runtimeContext.docker_outdir or "/var/spool/cwl"
            tmpdir = runtimeContext.docker_tmpdir or "/tmp"
            stagedir = runtimeContext.docker_stagedir or "/var/lib/cwl"
        else:
            outdir = fs_access.realpath(runtimeContext.outdir or
                tempfile.mkdtemp(prefix=getdefault(runtimeContext.tmp_outdir_prefix,
                                                   DEFAULT_TMP_PREFIX)))
            if self.tool[u"class"] != 'Workflow':
                tmpdir = fs_access.realpath(runtimeContext.tmpdir or tempfile.mkdtemp())
                stagedir = fs_access.realpath(runtimeContext.stagedir or tempfile.mkdtemp())

        builder = Builder(job,
                          files,
                          bindings,
                          self.schemaDefs,
                          self.names,
                          self.requirements,
                          self.hints,
                          runtimeContext.eval_timeout,
                          runtimeContext.debug,
                          {},
                          runtimeContext.js_console,
                          runtimeContext.mutation_manager,
                          self.formatgraph,
                          make_fs_access,
                          fs_access,
                          runtimeContext.force_docker_pull,
                          loadListing,
                          outdir,
                          tmpdir,
                          stagedir,
                          runtimeContext.job_script_provider)

        bindings.extend(builder.bind_input(
            self.inputs_record_schema, job,
            discover_secondaryFiles=getdefault(runtimeContext.toplevel, False)))

        if self.tool.get("baseCommand"):
            for n, b in enumerate(aslist(self.tool["baseCommand"])):
                bindings.append({
                    "position": [-1000000, n],
                    "datum": b
                })

        if self.tool.get("arguments"):
            for i, a in enumerate(self.tool["arguments"]):
                lc = self.tool["arguments"].lc.data[i]
                fn = self.tool["arguments"].lc.filename
                bindings.lc.add_kv_line_col(len(bindings), lc)
                if isinstance(a, dict):
                    a = copy.copy(a)
                    if a.get("position"):
                        a["position"] = [a["position"], i]
                    else:
                        a["position"] = [0, i]
                    bindings.append(a)
                elif ("$(" in a) or ("${" in a):
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("valueFrom", a)
                    ))
                    cm.lc.add_kv_line_col("valueFrom", lc)
                    cm.lc.filename = fn
                    bindings.append(cm)
                else:
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("datum", a)
                    ))
                    cm.lc.add_kv_line_col("datum", lc)
                    cm.lc.filename = fn
                    bindings.append(cm)

        # use python2 like sorting of heterogeneous lists
        # (containing str and int types),
        # TODO: unify for both runtime
        if six.PY3:
            key = cmp_to_key(cmp_like_py2)
        else:  # PY2
            key = lambda dict: dict["position"]
        bindings.sort(key=key)

        if self.tool[u"class"] != 'Workflow':
            builder.resources = self.evalResources(builder, runtimeContext)
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

            if mn:
                request[a + "Min"] = cast(int, mn)
                request[a + "Max"] = cast(int, mx)

        if runtimeContext.select_resources:
            return runtimeContext.select_resources(request, runtimeContext)
        else:
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

    def visit(self, op):  # type: (Callable[[Dict[Text, Any]], None]) -> None
        op(self.tool)

    @abc.abstractmethod
    def job(self,
            job_order,         # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            runtimeContext     # type: RuntimeContext
           ):  # type: (...) -> Generator[Any, None, None]
        # FIXME: Declare base type for what Generator yields
        pass


def empty_subtree(dirpath):  # type: (Text) -> bool
    # Test if a directory tree contains any files (does not count empty
    # subdirectories)
    for d in os.listdir(dirpath):
        d = os.path.join(dirpath, d)
        try:
            if stat.S_ISDIR(os.stat(d).st_mode):
                if empty_subtree(d) is False:
                    return False
            else:
                return False
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
    return True


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


def scandeps(base, doc, reffields, urlfields, loadref, urljoin=urllib.parse.urljoin):
    # type: (Text, Any, Set[Text], Set[Text], Callable[[Text, Text], Any], Callable[[Text, Text], Text]) -> List[Dict[Text, Text]]
    r = []  # type: List[Dict[Text, Text]]
    if isinstance(doc, dict):
        if "id" in doc:
            if doc["id"].startswith("file://"):
                df, _ = urllib.parse.urldefrag(doc["id"])
                if base != df:
                    r.append({
                        "class": "File",
                        "location": df
                    })
                    base = df

        if doc.get("class") in ("File", "Directory") and "location" in urlfields:
            u = doc.get("location", doc.get("path"))
            if u and not u.startswith("_:"):
                deps = {"class": doc["class"],"location": urljoin(base, u)
                       }  # type: Dict[Text, Any]
                if "basename" in doc:
                    deps["basename"] = doc["basename"]
                if doc["class"] == "Directory" and "listing" in doc:
                    deps["listing"] = doc["listing"]
                if doc["class"] == "File" and "secondaryFiles" in doc:
                    deps["secondaryFiles"] = doc["secondaryFiles"]
                deps = nestdir(base, deps)
                r.append(deps)
            else:
                if doc["class"] == "Directory" and "listing" in doc:
                    r.extend(scandeps(base, doc["listing"], reffields, urlfields, loadref, urljoin=urljoin))
                elif doc["class"] == "File" and "secondaryFiles" in doc:
                    r.extend(scandeps(base, doc["secondaryFiles"], reffields, urlfields, loadref, urljoin=urljoin))

        for k, v in iteritems(doc):
            if k in reffields:
                for u in aslist(v):
                    if isinstance(u, dict):
                        r.extend(scandeps(base, u, reffields, urlfields, loadref, urljoin=urljoin))
                    else:
                        sub = loadref(base, u)
                        subid = urljoin(base, u)
                        deps = {
                            "class": "File",
                            "location": subid
                        }
                        sf = scandeps(subid, sub, reffields, urlfields, loadref, urljoin=urljoin)
                        if sf:
                            deps["secondaryFiles"] = sf
                        deps = nestdir(base, deps)
                        r.append(deps)
            elif k in urlfields and k != "location":
                for u in aslist(v):
                    deps = {
                        "class": "File",
                        "location": urljoin(base, u)
                    }
                    deps = nestdir(base, deps)
                    r.append(deps)
            elif k not in ("listing", "secondaryFiles"):
                r.extend(scandeps(base, v, reffields, urlfields, loadref, urljoin=urljoin))
    elif isinstance(doc, list):
        for d in doc:
            r.extend(scandeps(base, d, reffields, urlfields, loadref, urljoin=urljoin))

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
            f.seek(0, 2)
            filesize = f.tell()
        fileobj["checksum"] = "sha1$%s" % checksum.hexdigest()
        fileobj["size"] = filesize
