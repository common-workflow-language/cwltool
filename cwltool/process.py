import abc
import avro.schema
import os
import json
import schema_salad.validate as validate
import copy
import yaml
import copy
import logging
import pprint
from .utils import aslist, get_feature
import schema_salad.schema
from schema_salad.ref_resolver import Loader
import urlparse
import pprint
from pkg_resources import resource_stream
import stat
from .builder import Builder, adjustFileObjs
import tempfile
import glob
from .errors import WorkflowException
from .pathmapper import abspath
from typing import Any, Callable, Generator, Union, IO, AnyStr, Tuple
from collections import Iterable
from rdflib import URIRef
from rdflib.namespace import RDFS, OWL
from .stdfsaccess import StdFsAccess
import errno
from rdflib import Graph

_logger = logging.getLogger("cwltool")

supportedProcessRequirements = ["DockerRequirement",
                                "SchemaDefRequirement",
                                "EnvVarRequirement",
                                "CreateFileRequirement",
                                "ScatterFeatureRequirement",
                                "SubworkflowFeatureRequirement",
                                "MultipleInputFeatureRequirement",
                                "InlineJavascriptRequirement",
                                "ShellCommandRequirement",
                                "StepInputExpressionRequirement",
                                "ResourceRequirement"]

cwl_files = ("Workflow.yml",
              "CommandLineTool.yml",
              "CommonWorkflowLanguage.yml",
              "Process.yml",
              "concepts.md",
              "contrib.md",
              "intro.md",
              "invocation.md")

salad_files = ('metaschema.yml',
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

SCHEMA_CACHE = {}  # type: Dict[str, Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[unicode,Any], Loader]]
SCHEMA_FILE = None
SCHEMA_ANY = None

def get_schema(version):
    # type: (str) -> Tuple[Loader, Union[avro.schema.Names, avro.schema.SchemaParseException], Dict[unicode,Any], Loader]

    if version in SCHEMA_CACHE:
        return SCHEMA_CACHE[version]

    cache = {}
    version = version.split("#")[-1].split(".")[0]
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

    global SCHEMA_FILE, SCHEMA_ANY  # pylint: disable=global-statement
    SCHEMA_FILE = SCHEMA_CACHE[version][3].idx["https://w3id.org/cwl/cwl#File"]
    SCHEMA_ANY = SCHEMA_CACHE[version][3].idx["https://w3id.org/cwl/salad#Any"]

    return SCHEMA_CACHE[version]

def shortname(inputid):
    # type: (Union[str, unicode]) -> str
    d = urlparse.urlparse(inputid)
    if d.fragment:
        return d.fragment.split("/")[-1].split(".")[-1]
    else:
        return d.path.split("/")[-1]


class UnsupportedRequirement(Exception):
    pass

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

def adjustFiles(rec, op):  # type: (Any, Callable[..., Any]) -> None
    """Apply a mapping function to each File path in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"])
        for d in rec:
            adjustFiles(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFiles(d, op)

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
    # type: (Union[Dict[str, Any], List[Dict[str, Any]]], Any, Graph) -> None
    for af in aslist(actualFile):
        if "format" not in af:
            raise validate.ValidationException(u"Missing required 'format' for File %s" % af)
        for inpf in aslist(inputFormats):
            if af["format"] == inpf or formatSubclassOf(af["format"], inpf, ontology, set()):
                return
        raise validate.ValidationException(u"Incompatible file format %s required format(s) %s" % (af["format"], inputFormats))

def fillInDefaults(inputs, job):
    # type: (List[Dict[str, str]], Dict[str, str]) -> None
    for inp in inputs:
        if shortname(inp["id"]) in job:
            pass
        elif shortname(inp["id"]) not in job and "default" in inp:
            job[shortname(inp["id"])] = copy.copy(inp["default"])
        elif shortname(inp["id"]) not in job and inp["type"][0] == "null":
            pass
        else:
            raise validate.ValidationException("Missing input parameter `%s`" % shortname(inp["id"]))

class Process(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[str, Any], **Any) -> None
        self.metadata = kwargs.get("metadata", {})  # type: Dict[str,Any]
        self.names = None  # type: avro.schema.Names
        names = schema_salad.schema.make_avro_schema(
            [SCHEMA_FILE, SCHEMA_ANY], schema_salad.ref_resolver.Loader({}))[0]
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
            av = schema_salad.schema.make_valid_avro(sdtypes, {t["name"]: t for t in sdtypes}, set())
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
        # type: (Dict[str, str], str, **Any) -> Builder
        builder = Builder()
        builder.job = copy.deepcopy(joborder)

        fillInDefaults(self.tool["inputs"], builder.job)

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

        dockerReq, _ = self.get_requirement("DockerRequirement")
        if dockerReq and kwargs.get("use_container"):
            builder.outdir = kwargs.get("docker_outdir") or "/var/spool/cwl"
            builder.tmpdir = kwargs.get("docker_tmpdir") or "/tmp"
        else:
            builder.outdir = kwargs.get("outdir") or tempfile.mkdtemp()
            builder.tmpdir = kwargs.get("tmpdir") or tempfile.mkdtemp()

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
        # type: (List[Dict[str, Any]], bool) -> None
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
        # type: (Dict[str, str], str, Callable[[Any, Any], Any], **Any) -> Generator[Any, None, None]
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

def scandeps(base, doc, reffields, urlfields, loadref):
    # type: (str, Any, Set[str], Set[str], Callable[[str, str], Any]) -> List[Dict[str, str]]
    r = []
    if isinstance(doc, dict):
        if "id" in doc:
            if doc["id"].startswith("file://"):
                df, _ = urlparse.urldefrag(doc["id"])
                if base != df:
                    r.append({
                        "class": "File",
                        "path": df
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
                            "path": subid
                            }  # type: Dict[str, Any]
                        sf = scandeps(subid, sub, reffields, urlfields, loadref)
                        if sf:
                            deps["secondaryFiles"] = sf
                        r.append(deps)
            elif k in urlfields:
                for u in aslist(v):
                    r.append({
                        "class": "File",
                        "path": urlparse.urljoin(base, u)
                    })
            else:
                r.extend(scandeps(base, v, reffields, urlfields, loadref))
    elif isinstance(doc, list):
        for d in doc:
            r.extend(scandeps(base, d, reffields, urlfields, loadref))
    return r
