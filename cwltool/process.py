import os
import json
import copy
import logging
import pprint
import stat
import tempfile
import glob
import urlparse
from collections import Iterable
import errno
import shutil
import uuid
import hashlib

import abc
import schema_salad.validate as validate
import schema_salad.schema
from schema_salad.ref_resolver import Loader
from schema_salad.sourceline import SourceLine
import avro.schema
from typing import (Any, AnyStr, Callable, cast, Dict, List, Generator, IO, Text,
        Tuple, Union)
from rdflib import URIRef
from rdflib.namespace import RDFS, OWL
from rdflib import Graph
from pkg_resources import resource_stream


from ruamel.yaml.comments import CommentedSeq, CommentedMap

from .utils import aslist, get_feature
from .stdfsaccess import StdFsAccess
from .builder import Builder, adjustFileObjs, adjustDirObjs
from .errors import WorkflowException, UnsupportedRequirement
from .pathmapper import PathMapper, abspath, normalizeFilesDirs

_logger = logging.getLogger("cwltool")

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
                                "InitialWorkDirRequirement"]

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

SCHEMA_CACHE = {}  # type: Dict[Text, Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[Text, Any], Loader]]
SCHEMA_FILE = None  # type: Dict[Text, Any]
SCHEMA_DIR = None  # type: Dict[Text, Any]
SCHEMA_ANY = None  # type: Dict[Text, Any]

def get_schema(version):
    # type: (Text) -> Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[Text,Any], Loader]

    if version in SCHEMA_CACHE:
        return SCHEMA_CACHE[version]

    cache = {}
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

    SCHEMA_CACHE[version] = schema_salad.schema.load_schema(
        "https://w3id.org/cwl/CommonWorkflowLanguage.yml", cache=cache)

    return SCHEMA_CACHE[version]

def shortname(inputid):
    # type: (Text) -> Text
    d = urlparse.urlparse(inputid)
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

def getListing(fs_access, rec):
    # type: (StdFsAccess, Dict[Text, Any]) -> None
    if "listing" not in rec:
        listing = []
        loc = rec["location"]
        for ld in fs_access.listdir(loc):
            if fs_access.isdir(ld):
                ent = {u"class": u"Directory",
                       u"location": ld}
                getListing(fs_access, ent)
                listing.append(ent)
            else:
                listing.append({"class": "File", "location": ld})
        rec["listing"] = listing

def stageFiles(pm, stageFunc, ignoreWritable=False):
    # type: (PathMapper, Callable[..., Any], bool) -> None
    for f, p in pm.items():
        if not os.path.exists(os.path.dirname(p.target)):
            os.makedirs(os.path.dirname(p.target), 0755)
        if p.type == "File":
            stageFunc(p.resolved, p.target)
        elif p.type == "WritableFile" and not ignoreWritable:
            shutil.copy(p.resolved, p.target)
        elif p.type == "CreateFile" and not ignoreWritable:
            with open(p.target, "w") as n:
                n.write(p.resolved.encode("utf-8"))

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

def relocateOutputs(outputObj, outdir, output_dirs, action):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Set[Text], Text) -> Union[Dict[Text, Any], List[Dict[Text, Any]]]
    if action not in ("move", "copy"):
        return outputObj

    def moveIt(src, dst):
        if action == "move":
            for a in output_dirs:
                if src.startswith(a):
                    _logger.debug("Moving %s to %s", src, dst)
                    shutil.move(src, dst)
                    return
        _logger.debug("Copying %s to %s", src, dst)
        shutil.copy(src, dst)

    outfiles = []  # type: List[Dict[Text, Any]]
    collectFilesAndDirs(outputObj, outfiles)
    pm = PathMapper(outfiles, "", outdir, separateDirs=False)
    stageFiles(pm, moveIt)

    def _check_adjust(f):
        f["location"] = "file://" + pm.mapper(f["location"])[1]
        if "contents" in f:
            del f["contents"]
        if f["class"] == "File":
            compute_checksums(StdFsAccess(""), f)
        return f

    adjustFileObjs(outputObj, _check_adjust)
    adjustDirObjs(outputObj, _check_adjust)

    return outputObj

def cleanIntermediate(output_dirs):  # type: (Set[Text]) -> None
    for a in output_dirs:
        if os.path.exists(a) and empty_subtree(a):
            _logger.debug(u"Removing intermediate output directory %s", a)
            shutil.rmtree(a, True)


def formatSubclassOf(fmt, cls, ontology, visited):
    # type: (Text, Text, Graph, Set[Text]) -> bool
    """Determine if `fmt` is a subclass of `cls`."""

    if URIRef(fmt) == URIRef(cls):
        return True

    if ontology is None:
        return False

    if fmt in visited:
        return False

    visited.add(fmt)

    uriRefFmt = URIRef(fmt)

    for s,p,o in ontology.triples( (uriRefFmt, RDFS.subClassOf, None) ):
        # Find parent classes of `fmt` and search upward
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for s,p,o in ontology.triples( (uriRefFmt, OWL.equivalentClass, None) ):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for s,p,o in ontology.triples( (None, OWL.equivalentClass, uriRefFmt) ):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(s, cls, ontology, visited):
            return True

    return False


def checkFormat(actualFile, inputFormats, ontology):
    # type: (Union[Dict[Text, Any], List, Text], Union[List[Text], Text], Graph) -> None
    for af in aslist(actualFile):
        if "format" not in af:
            raise validate.ValidationException(u"Missing required 'format' for File %s" % af)
        for inpf in aslist(inputFormats):
            if af["format"] == inpf or formatSubclassOf(af["format"], inpf, ontology, set()):
                return
        raise validate.ValidationException(u"Incompatible file format %s required format(s) %s" % (af["format"], inputFormats))

def fillInDefaults(inputs, job):
    # type: (List[Dict[Text, Text]], Dict[Text, Union[Dict[Text, Any], List, Text]]) -> None
    for e, inp in enumerate(inputs):
        with SourceLine(inputs, e, WorkflowException):
            if shortname(inp[u"id"]) in job:
                pass
            elif shortname(inp[u"id"]) not in job and u"default" in inp:
                job[shortname(inp[u"id"])] = copy.copy(inp[u"default"])
            elif shortname(inp[u"id"]) not in job and aslist(inp[u"type"])[0] == u"null":
                pass
            else:
                raise WorkflowException("Missing required input parameter `%s`" % shortname(inp["id"]))


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
                field_type["name"] = name_prefix+Text(uuid.uuid4())
        if field_type["type"] == "record":
            avroize_type(field_type["fields"], name_prefix)
        if field_type["type"] == "array":
            avroize_type(field_type["items"], name_prefix)
    return field_type

class Process(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[Text, Any], **Any) -> None
        """
        kwargs:

        metadata: tool document metadata
        requirements: inherited requirements
        hints: inherited hints
        loader: schema_salad.ref_resolver.Loader used to load tool document
        avsc_names: CWL Avro schema object used to validate document
        strict: flag to determine strict validation (fail on unrecognized fields)
        """

        self.metadata = kwargs.get("metadata", {})  # type: Dict[Text,Any]
        self.names = None  # type: avro.schema.Names

        global SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY  # pylint: disable=global-statement
        if SCHEMA_FILE is None:
            get_schema("v1.0")
            SCHEMA_ANY = cast(Dict[Text, Any],
                    SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/salad#Any"])
            SCHEMA_FILE = cast(Dict[Text, Any],
                    SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#File"])
            SCHEMA_DIR = cast(Dict[Text, Any],
                              SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#Directory"])

        names = schema_salad.schema.make_avro_schema([SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY],
                                                     schema_salad.ref_resolver.Loader({}))[0]
        if isinstance(names, avro.schema.SchemaParseException):
            raise names
        else:
            self.names = names
        self.tool = toolpath_object
        self.requirements = kwargs.get("requirements", []) + self.tool.get("requirements", [])
        self.hints = kwargs.get("hints", []) + self.tool.get("hints", [])
        self.formatgraph = None  # type: Graph
        if "loader" in kwargs:
            self.formatgraph = kwargs["loader"].graph

        self.doc_loader = kwargs["loader"]
        self.doc_schema = kwargs["avsc_names"]

        checkRequirements(self.tool, supportedProcessRequirements)
        self.validate_hints(kwargs["avsc_names"], self.tool.get("hints", []),
                strict=kwargs.get("strict"))

        self.schemaDefs = {}  # type: Dict[Text,Dict[Text, Any]]

        sd, _ = self.get_requirement("SchemaDefRequirement")

        if sd:
            sdtypes = sd["types"]
            av = schema_salad.schema.make_valid_avro(sdtypes, {t["name"]: t for t in avroize_type(sdtypes)}, set())
            for i in av:
                self.schemaDefs[i["name"]] = i
            avro.schema.make_avsc_object(av, self.names)

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
                    raise validate.ValidationException(u"Missing `type` in parameter `%s`" % c["name"])

                if "default" in c and "null" not in aslist(c["type"]):
                    c["type"] = ["null"] + aslist(c["type"])
                else:
                    c["type"] = c["type"]
                c["type"] = avroize_type(c["type"], c["name"])
                if key == "inputs":
                    self.inputs_record_schema["fields"].append(c)
                elif key == "outputs":
                    self.outputs_record_schema["fields"].append(c)

        try:
            self.inputs_record_schema = schema_salad.schema.make_valid_avro(self.inputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.inputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException(u"Got error `%s` while processing inputs of %s:\n%s" % (Text(e), self.tool["id"], json.dumps(self.inputs_record_schema, indent=4)))

        try:
            self.outputs_record_schema = schema_salad.schema.make_valid_avro(self.outputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.outputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException(u"Got error `%s` while processing outputs of %s:\n%s" % (Text(e), self.tool["id"], json.dumps(self.outputs_record_schema, indent=4)))


    def _init_job(self, joborder, **kwargs):
        # type: (Dict[Text, Text], **Any) -> Builder
        """
        kwargs:

        eval_timeout: javascript evaluation timeout
        use_container: do/don't use Docker when DockerRequirement hint provided
        make_fs_access: make an FsAccess() object with given basedir
        basedir: basedir for FsAccess
        docker_outdir: output directory inside docker for this job
        docker_tmpdir: tmpdir inside docker for this job
        docker_stagedir: stagedir inside docker for this job
        outdir: outdir on host for this job
        tmpdir: tmpdir on host for this job
        stagedir: stagedir on host for this job
        select_resources: callback to select compute resources
        """

        builder = Builder()
        builder.job = cast(Dict[Text, Union[Dict[Text, Any], List,
            Text]], copy.deepcopy(joborder))

        # Validate job order
        try:
            fillInDefaults(self.tool[u"inputs"], builder.job)
            normalizeFilesDirs(builder.job)
            validate.validate_ex(self.names.get_name("input_record_schema", ""), builder.job)
        except (validate.ValidationException, WorkflowException) as e:
            raise WorkflowException("Invalid job input record:\n" + Text(e))

        builder.files = []
        builder.bindings = CommentedSeq()
        builder.schemaDefs = self.schemaDefs
        builder.names = self.names
        builder.requirements = self.requirements
        builder.hints = self.hints
        builder.resources = {}
        builder.timeout = kwargs.get("eval_timeout")
        builder.debug = kwargs.get("debug")

        dockerReq, is_req = self.get_requirement("DockerRequirement")

        if dockerReq and is_req and not kwargs.get("use_container"):
            raise WorkflowException("Document has DockerRequirement under 'requirements' but use_container is false.  DockerRequirement must be under 'hints' or use_container must be true.")

        builder.make_fs_access = kwargs.get("make_fs_access") or StdFsAccess
        builder.fs_access = builder.make_fs_access(kwargs["basedir"])

        if dockerReq and kwargs.get("use_container"):
            builder.outdir = builder.fs_access.realpath(dockerReq.get("dockerOutputDirectory") or kwargs.get("docker_outdir") or "/var/spool/cwl")
            builder.tmpdir = builder.fs_access.realpath(kwargs.get("docker_tmpdir") or "/tmp")
            builder.stagedir = builder.fs_access.realpath(kwargs.get("docker_stagedir") or "/var/lib/cwl")
        else:
            builder.outdir = builder.fs_access.realpath(kwargs.get("outdir") or tempfile.mkdtemp())
            builder.tmpdir = builder.fs_access.realpath(kwargs.get("tmpdir") or tempfile.mkdtemp())
            builder.stagedir = builder.fs_access.realpath(kwargs.get("stagedir") or tempfile.mkdtemp())

        if self.formatgraph:
            for i in self.tool["inputs"]:
                d = shortname(i["id"])
                if d in builder.job and i.get("format"):
                    checkFormat(builder.job[d], builder.do_eval(i["format"]), self.formatgraph)

        builder.bindings.extend(builder.bind_input(self.inputs_record_schema, builder.job))

        if self.tool.get("baseCommand"):
            for n, b in enumerate(aslist(self.tool["baseCommand"])):
                builder.bindings.append({
                    "position": [-1000000, n],
                    "datum": b
                })

        if self.tool.get("arguments"):
            for i, a in enumerate(self.tool["arguments"]):
                lc = self.tool["arguments"].lc.data[i]
                fn = self.tool["arguments"].lc.filename
                builder.bindings.lc.add_kv_line_col(len(builder.bindings), lc)
                if isinstance(a, dict):
                    a = copy.copy(a)
                    if a.get("position"):
                        a["position"] = [a["position"], i]
                    else:
                        a["position"] = [0, i]
                    builder.bindings.append(a)
                elif ("$(" in a) or ("${" in a):
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("valueFrom", a)
                    ))
                    cm.lc.add_kv_line_col("valueFrom", lc)
                    cm.lc.filename = fn
                    builder.bindings.append(cm)
                else:
                    cm = CommentedMap((
                        ("position", [0, i]),
                        ("datum", a)
                    ))
                    cm.lc.add_kv_line_col("datum", lc)
                    cm.lc.filename = fn
                    builder.bindings.append(cm)

        builder.bindings.sort(key=lambda a: a["position"])

        builder.resources = self.evalResources(builder, kwargs)

        return builder

    def evalResources(self, builder, kwargs):
        # type: (Builder, Dict[AnyStr, Any]) -> Dict[Text, Union[int, Text]]
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
        }
        for a in ("cores", "ram", "tmpdir", "outdir"):
            mn = None
            mx = None
            if resourceReq.get(a+"Min"):
                mn = builder.do_eval(resourceReq[a+"Min"])
            if resourceReq.get(a+"Max"):
                mx = builder.do_eval(resourceReq[a+"Max"])
            if mn is None:
                mn = mx
            elif mx is None:
                mx = mn

            if mn:
                request[a+"Min"] = mn
                request[a+"Max"] = mx

        if kwargs.get("select_resources"):
            return kwargs["select_resources"](request)
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
                if avsc_names.get_name(r["class"], "") is not None:
                    plain_hint = dict((key,r[key]) for key in r if key not in
                            self.doc_loader.identifiers)  # strip identifiers
                    validate.validate_ex(
                        avsc_names.get_name(plain_hint["class"], ""),
                        plain_hint, strict=strict)
                else:
                    _logger.info(sl.makeError(u"Unknown hint %s" % (r["class"])))

    def get_requirement(self, feature):  # type: (Any) -> Tuple[Any, bool]
        return get_feature(self, feature)

    def visit(self, op):  # type: (Callable[[Dict[Text, Any]], None]) -> None
        op(self.tool)

    @abc.abstractmethod
    def job(self, job_order, output_callbacks, **kwargs):
        # type: (Dict[Text, Text], Callable[[Any, Any], Any], **Any) -> Generator[Any, None, None]
        return None

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


def uniquename(stem):  # type: (Text) -> Text
    c = 1
    u = stem
    while u in _names:
        c += 1
        u = u"%s_%s" % (stem, c)
    _names.add(u)
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
    for e in listing:
        if e["basename"] not in ents:
            ents[e["basename"]] = e
        elif e["class"] == "Directory":
            ents[e["basename"]]["listing"].extend(e["listing"])
    for e in ents.itervalues():
        if e["class"] == "Directory" and "listing" in e:
            e["listing"] = mergedirs(e["listing"])
    r.extend(ents.itervalues())
    return r

def scandeps(base, doc, reffields, urlfields, loadref, urljoin=urlparse.urljoin):
    # type: (Text, Any, Set[Text], Set[Text], Callable[[Text, Text], Any], Callable[[Text, Text], Text]) -> List[Dict[Text, Text]]
    r = []  # type: List[Dict[Text, Text]]
    deps = None  # type: Dict[Text, Any]
    if isinstance(doc, dict):
        if "id" in doc:
            if doc["id"].startswith("file://"):
                df, _ = urlparse.urldefrag(doc["id"])
                if base != df:
                    r.append({
                        "class": "File",
                        "location": df
                    })
                    base = df

        if doc.get("class") in ("File", "Directory") and "location" in urlfields:
            u = doc.get("location", doc.get("path"))
            if u and not u.startswith("_:"):
                deps = {
                    "class": doc["class"],
                    "location": urljoin(base, u)
                }
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

        for k, v in doc.iteritems():
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
            contents = f.read(1024*1024)
            while contents != "":
                checksum.update(contents)
                contents = f.read(1024*1024)
            f.seek(0, 2)
            filesize = f.tell()
        fileobj["checksum"] = "sha1$%s" % checksum.hexdigest()
        fileobj["size"] = filesize
