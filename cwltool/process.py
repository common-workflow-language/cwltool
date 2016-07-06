
import os
import json
import copy
import logging
import pprint
import stat
import tempfile
import glob
import urlparse
import pprint
from collections import Iterable
import errno
import shutil
import uuid

import abc
import schema_salad.validate as validate
import schema_salad.schema
from schema_salad.ref_resolver import Loader
import avro.schema
from typing import (Any, AnyStr, Callable, cast, Dict, List, Generator, IO,
        Tuple, Union)
from rdflib import URIRef
from rdflib.namespace import RDFS, OWL
from rdflib import Graph
from pkg_resources import resource_stream

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

cwl_files = ("Workflow.yml",
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

SCHEMA_CACHE = {}  # type: Dict[str, Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[unicode, Any], Loader]]
SCHEMA_FILE = None  # type: Dict[unicode, Any]
SCHEMA_DIR = None  # type: Dict[unicode, Any]
SCHEMA_ANY = None  # type: Dict[unicode, Any]

def get_schema(version):
    # type: (str) -> Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[unicode,Any], Loader]

    if version in SCHEMA_CACHE:
        return SCHEMA_CACHE[version]

    cache = {}
    version = version.split("#")[-1]
    if 'dev' in version:
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
    # type: (unicode) -> unicode
    d = urlparse.urlparse(inputid)
    if d.fragment:
        return d.fragment.split(u"/")[-1]
    else:
        return d.path.split(u"/")[-1]

def checkRequirements(rec, supportedProcessRequirements):
    # type: (Any, Iterable[Any]) -> None
    if isinstance(rec, dict):
        if "requirements" in rec:
            for r in rec["requirements"]:
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
    # type: (StdFsAccess, Dict[str, Any]) -> None
    if "listing" not in rec:
        listing = []
        loc = rec["location"]
        for ld in fs_access.listdir(loc):
            if fs_access.isdir(ld):
                ent = {"class": "Directory",
                       "location": ld}
                getListing(fs_access, ent)
                listing.append(ent)
            else:
                listing.append({"class": "File", "location": ld})
        rec["listing"] = listing

def stageFiles(pm, stageFunc):
    # type: (PathMapper, Callable[..., Any]) -> None
    for f, p in pm.items():
        if not os.path.exists(os.path.dirname(p.target)):
            os.makedirs(os.path.dirname(p.target), 0755)
        if p.type == "File":
            stageFunc(p.resolved, p.target)
        elif p.type == "WritableFile":
            shutil.copy(p.resolved, p.target)
        elif p.type == "CreateFile":
            with open(p.target, "w") as n:
                n.write(p.resolved.encode("utf-8"))

def collectFilesAndDirs(obj, out):
    # type: (Union[Dict[unicode, Any], List[Dict[unicode, Any]]], List[Dict[unicode, Any]]) -> None
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
    # type: (Union[Dict[unicode, Any], List[Dict[unicode, Any]]], unicode, Set[unicode], unicode) -> Union[Dict[unicode, Any], List[Dict[unicode, Any]]]
    if action not in ("move", "copy"):
        return outputObj

    def moveIt(src, dst):
        for a in output_dirs:
            if src.startswith(a):
                if action == "move":
                    _logger.debug("Moving %s to %s", src, dst)
                    shutil.move(src, dst)
                elif action == "copy":
                    _logger.debug("Copying %s to %s", src, dst)
                    shutil.copy(src, dst)

    outfiles = []  # type: List[Dict[unicode, Any]]
    collectFilesAndDirs(outputObj, outfiles)
    pm = PathMapper(outfiles, "", outdir, separateDirs=False)
    stageFiles(pm, moveIt)

    def _check_adjust(f):
        f["location"] = "file://" + pm.mapper(f["location"])[1]
        return f

    adjustFileObjs(outputObj, _check_adjust)
    adjustDirObjs(outputObj, _check_adjust)

    return outputObj

def cleanIntermediate(output_dirs):  # type: (Set[unicode]) -> None
    for a in output_dirs:
        if os.path.exists(a) and empty_subtree(a):
            _logger.debug(u"Removing intermediate output directory %s", a)
            shutil.rmtree(a, True)


def formatSubclassOf(fmt, cls, ontology, visited):
    # type: (str, str, Graph, Set[str]) -> bool
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
    # type: (Union[Dict[unicode, Any], List, unicode], Union[List[unicode], unicode], Graph) -> None
    for af in aslist(actualFile):
        if "format" not in af:
            raise validate.ValidationException(u"Missing required 'format' for File %s" % af)
        for inpf in aslist(inputFormats):
            if af["format"] == inpf or formatSubclassOf(af["format"], inpf, ontology, set()):
                return
        raise validate.ValidationException(u"Incompatible file format %s required format(s) %s" % (af["format"], inputFormats))

def fillInDefaults(inputs, job):
    # type: (List[Dict[unicode, unicode]], Dict[unicode, Union[Dict[unicode, Any], List, unicode]]) -> None
    for inp in inputs:
        if shortname(inp[u"id"]) in job:
            pass
        elif shortname(inp[u"id"]) not in job and u"default" in inp:
            job[shortname(inp[u"id"])] = copy.copy(inp[u"default"])
        elif shortname(inp[u"id"]) not in job and inp[u"type"][0] == u"null":
            pass
        else:
            raise validate.ValidationException("Missing input parameter `%s`" % shortname(inp["id"]))


def avroize_type(field_type, name_prefix=""):
    # type: (Union[List[Dict[unicode, Any]], Dict[unicode, Any]], unicode) -> Any
    """
    adds missing information to a type so that CWL types are valid in schema_salad.
    """
    if isinstance(field_type, list):
        for f in field_type:
            avroize_type(f, name_prefix)
    elif isinstance(field_type, dict):
        if field_type["type"] in ("enum", "record"):
            if "name" not in field_type:
                field_type["name"] = name_prefix+unicode(uuid.uuid4())
        if field_type["type"] == "record":
            avroize_type(field_type["fields"], name_prefix)
        if field_type["type"] == "array":
            avroize_type(field_type["items"], name_prefix)
    return field_type

class Process(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[unicode, Any], **Any) -> None
        self.metadata = kwargs.get("metadata", {})  # type: Dict[str,Any]
        self.names = None  # type: avro.schema.Names

        global SCHEMA_FILE, SCHEMA_DIR, SCHEMA_ANY  # pylint: disable=global-statement
        if SCHEMA_FILE is None:
            get_schema("v1.0")
            SCHEMA_ANY = cast(Dict[unicode, Any],
                    SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/salad#Any"])
            SCHEMA_FILE = cast(Dict[unicode, Any],
                    SCHEMA_CACHE["v1.0"][3].idx["https://w3id.org/cwl/cwl#File"])
            SCHEMA_DIR = cast(Dict[unicode, Any],
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

        checkRequirements(self.tool, supportedProcessRequirements)
        self.validate_hints(kwargs["avsc_names"], self.tool.get("hints", []), strict=kwargs.get("strict"))

        self.schemaDefs = {}  # type: Dict[str,Dict[unicode, Any]]

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
                "fields": []}  # type: Dict[unicode, Any]
        self.outputs_record_schema = {
                "name": "outputs_record_schema", "type": "record",
                "fields": []}  # type: Dict[unicode, Any]

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
                    self.inputs_record_schema["fields"].append(c)  # type: ignore
                elif key == "outputs":
                    self.outputs_record_schema["fields"].append(c)  # type: ignore

        try:
            self.inputs_record_schema = schema_salad.schema.make_valid_avro(self.inputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.inputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException(u"Got error `%s` while prcoessing inputs of %s:\n%s" % (str(e), self.tool["id"], json.dumps(self.inputs_record_schema, indent=4)))

        try:
            self.outputs_record_schema = schema_salad.schema.make_valid_avro(self.outputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.outputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException(u"Got error `%s` while prcoessing outputs of %s:\n%s" % (str(e), self.tool["id"], json.dumps(self.outputs_record_schema, indent=4)))


    def _init_job(self, joborder, **kwargs):
        # type: (Dict[unicode, unicode], **Any) -> Builder
        builder = Builder()
        builder.job = cast(Dict[unicode, Union[Dict[unicode, Any], List,
            unicode]], copy.deepcopy(joborder))

        fillInDefaults(self.tool[u"inputs"], builder.job)
        normalizeFilesDirs(builder.job)

        # Validate job order
        try:
            validate.validate_ex(self.names.get_name("input_record_schema", ""), builder.job)
        except validate.ValidationException as e:
            raise WorkflowException("Error validating input record, " + str(e))

        builder.files = []
        builder.bindings = []
        builder.schemaDefs = self.schemaDefs
        builder.names = self.names
        builder.requirements = self.requirements
        builder.resources = {}
        builder.timeout = kwargs.get("eval_timeout")

        dockerReq, is_req = self.get_requirement("DockerRequirement")

        if dockerReq and is_req and not kwargs.get("use_container"):
            raise WorkflowException("Document has DockerRequirement under 'requirements' but use_container is false.  DockerRequirement must be under 'hints' or use_container must be true.")

        if dockerReq and kwargs.get("use_container"):
            builder.outdir = kwargs.get("docker_outdir") or "/var/spool/cwl"
            builder.tmpdir = kwargs.get("docker_tmpdir") or "/tmp"
            builder.stagedir = kwargs.get("docker_stagedir") or "/var/lib/cwl"
        else:
            builder.outdir = kwargs.get("outdir") or tempfile.mkdtemp()
            builder.tmpdir = kwargs.get("tmpdir") or tempfile.mkdtemp()
            builder.stagedir = kwargs.get("stagedir") or tempfile.mkdtemp()

        builder.fs_access = kwargs.get("fs_access") or StdFsAccess(kwargs["basedir"])

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
                    "valueFrom": b
                })

        if self.tool.get("arguments"):
            for i, a in enumerate(self.tool["arguments"]):
                if isinstance(a, dict):
                    a = copy.copy(a)
                    if a.get("position"):
                        a["position"] = [a["position"], i]
                    else:
                        a["position"] = [0, i]
                    a["do_eval"] = a["valueFrom"]
                    a["valueFrom"] = None
                    builder.bindings.append(a)
                elif ("$(" in a) or ("${" in a):
                    builder.bindings.append({
                        "position": [0, i],
                        "do_eval": a,
                        "valueFrom": None
                    })
                else:
                    builder.bindings.append({
                        "position": [0, i],
                        "valueFrom": a
                    })

        builder.bindings.sort(key=lambda a: a["position"])

        builder.resources = self.evalResources(builder, kwargs)

        return builder

    def evalResources(self, builder, kwargs):
        # type: (Builder, Dict[str, Any]) -> Dict[str, Union[int, str]]
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
                "ram":   request["ramMin"],
                "tmpdirSize": request["tmpdirMin"],
                "outdirSize": request["outdirMin"],
            }

    def validate_hints(self, avsc_names, hints, strict):
        # type: (Any, List[Dict[str, Any]], bool) -> None
        for r in hints:
            try:
                if avsc_names.get_name(r["class"], "") is not None:
                    validate.validate_ex(avsc_names.get_name(r["class"], ""), r, strict=strict)
                else:
                    _logger.info(str(validate.ValidationException(
                    u"Unknown hint %s" % (r["class"]))))
            except validate.ValidationException as v:
                raise validate.ValidationException(u"Validating hint `%s`: %s" % (r["class"], str(v)))

    def get_requirement(self, feature):  # type: (Any) -> Tuple[Any, bool]
        return get_feature(self, feature)

    def visit(self, op):
        op(self.tool)

    @abc.abstractmethod
    def job(self, job_order, output_callbacks, **kwargs):
        # type: (Dict[unicode, unicode], Callable[[Any, Any], Any], **Any) -> Generator[Any, None, None]
        return None

def empty_subtree(dirpath):  # type: (AnyStr) -> bool
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

_names = set()  # type: Set[unicode]


def uniquename(stem):  # type: (unicode) -> unicode
    c = 1
    u = stem
    while u in _names:
        c += 1
        u = u"%s_%s" % (stem, c)
    _names.add(u)
    return u

def nestdir(base, deps):
    # type: (unicode, Dict[unicode, Any]) -> Dict[unicode, Any]
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
    # type: (List[Dict[unicode, Any]]) -> List[Dict[unicode, Any]]
    r = []  # type: List[Dict[unicode, Any]]
    ents = {}  # type: Dict[unicode, Any]
    for e in listing:
        if e["basename"] not in ents:
            ents[e["basename"]] = e
        elif e["class"] == "Directory":
            ents[e["basename"]]["listing"].extend(e["listing"])
    for e in ents.itervalues():
        if e["class"] == "Directory":
            e["listing"] = mergedirs(e["listing"])
    r.extend(ents.itervalues())
    return r

def scandeps(base, doc, reffields, urlfields, loadref):
    # type: (unicode, Any, Set[unicode], Set[unicode], Callable[[unicode, unicode], Any]) -> List[Dict[unicode, unicode]]
    r = []  # type: List[Dict[unicode, unicode]]
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

        for k, v in doc.iteritems():
            if k in reffields:
                for u in aslist(v):
                    if isinstance(u, dict):
                        r.extend(scandeps(base, u, reffields, urlfields, loadref))
                    else:
                        sub = loadref(base, u)
                        subid = urlparse.urljoin(base, u)
                        deps = {
                            "class": "File",
                            "location": subid
                        }  # type: Dict[unicode, Any]
                        sf = scandeps(subid, sub, reffields, urlfields, loadref)
                        if sf:
                            deps["secondaryFiles"] = sf
                        deps = nestdir(base, deps)
                        r.append(deps)
            elif k in urlfields:
                for u in aslist(v):
                    deps = {
                        "class": "File",
                        "location": urlparse.urljoin(base, u)
                    }
                    deps = nestdir(base, deps)
                    r.append(deps)
            else:
                r.extend(scandeps(base, v, reffields, urlfields, loadref))
    elif isinstance(doc, list):
        for d in doc:
            r.extend(scandeps(base, d, reffields, urlfields, loadref))

    normalizeFilesDirs(r)
    r = mergedirs(r)
    return r
