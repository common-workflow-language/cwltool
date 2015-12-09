import avro.schema
import os
import json
import schema_salad.validate as validate
import copy
import yaml
import copy
import logging
import pprint
from aslist import aslist
import schema_salad.schema
import urlparse
import pprint
from pkg_resources import resource_stream
import stat
from builder import Builder
import tempfile
import glob
from errors import WorkflowException
from pathmapper import abspath

from rdflib import URIRef
from rdflib.namespace import RDFS

import errno

_logger = logging.getLogger("cwltool")

supportedProcessRequirements = ["DockerRequirement",
                                "ExpressionEngineRequirement",
                                "SchemaDefRequirement",
                                "EnvVarRequirement",
                                "CreateFileRequirement",
                                "ScatterFeatureRequirement",
                                "SubworkflowFeatureRequirement",
                                "MultipleInputFeatureRequirement",
                                "InlineJavascriptRequirement",
                                "ShellCommandRequirement"]

def get_schema():
    f = resource_stream(__name__, 'schemas/draft-3/cwl-avro.yml')
    j = yaml.load(f)
    j["name"] = "https://w3id.org/cwl/cwl"
    return schema_salad.schema.load_schema(j)

def get_feature(self, feature):
    for t in reversed(self.requirements):
        if t["class"] == feature:
            return (t, True)
    for t in reversed(self.hints):
        if t["class"] == feature:
            return (t, False)
    return (None, None)

def shortname(inputid):
    (_, d) = urlparse.urldefrag(inputid)
    return d.split("/")[-1].split(".")[-1]

class StdFsAccess(object):
    def __init__(self, basedir):
        self.basedir = basedir

    def _abs(self, p):
        return abspath(p, self.basedir)

    def glob(self, pattern):
        return glob.glob(self._abs(pattern))

    def open(self, fn, mode):
        return open(self._abs(fn), mode)

    def exists(self, fn):
        return os.path.exists(self._abs(fn))

def checkRequirements(rec, supportedProcessRequirements):
    if isinstance(rec, dict):
        if "requirements" in rec:
            for r in rec["requirements"]:
                if r["class"] not in supportedProcessRequirements:
                    raise Exception("Unsupported requirement %s" % r["class"])
        if "scatter" in rec:
            if isinstance(rec["scatter"], list) and rec["scatter"] > 1:
                raise Exception("Unsupported complex scatter type '%s'" % rec.get("scatterMethod"))
        for d in rec:
            checkRequirements(rec[d], supportedProcessRequirements)
    if isinstance(rec, list):
        for d in rec:
            checkRequirements(d, supportedProcessRequirements)

def adjustFiles(rec, op):
    """Apply a mapping function to each File path in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"])
        for d in rec:
            adjustFiles(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFiles(d, op)

def formatSubclassOf(fmt, cls, ontology):
    if ontology is None:
        return False

    fmt = URIRef(fmt)

    for s,p,o in ontology.triples( (fmt, RDFS.subClassOf, None) ):
        if o == URIRef(cls):
            return True

    for s,p,o in ontology.triples( (fmt, RDFS.subClassOf, None) ):
        if formatSubclassOf(o, cls, ontology):
            return True

    return False

def checkFormat(actualFile, inputFormats, requirements, ontology):
    for af in aslist(actualFile):
        if "format" not in af:
            raise validate.ValidationException("Missing required 'format' for File %s" % af)
        for inpf in aslist(inputFormats):
            if af["format"] == inpf or formatSubclassOf(af["format"], inpf, ontology):
                return
        raise validate.ValidationException("Incompatible file format %s required format(s) %s" % (af["format"], inputFormats))

class Process(object):
    def __init__(self, toolpath_object, **kwargs):
        (_, self.names, _) = get_schema()
        self.tool = toolpath_object
        self.requirements = kwargs.get("requirements", []) + self.tool.get("requirements", [])
        self.hints = kwargs.get("hints", []) + self.tool.get("hints", [])
        self.loader = kwargs.get("loader")
        self.avsc_names = kwargs.get("avsc_names")

        self.validate_hints(self.tool.get("hints", []), strict=kwargs.get("strict"))

        self.schemaDefs = {}

        sd, _ = self.get_requirement("SchemaDefRequirement")

        if sd:
            sdtypes = sd["types"]
            av = schema_salad.schema.make_valid_avro(sdtypes, {t["name"]: t for t in sdtypes}, set())
            for i in av:
                self.schemaDefs[i["name"]] = i
            avro.schema.make_avsc_object(av, self.names)

        # Build record schema from inputs
        self.inputs_record_schema = {"name": "input_record_schema", "type": "record", "fields": []}
        self.outputs_record_schema = {"name": "outputs_record_schema", "type": "record", "fields": []}

        for key in ("inputs", "outputs"):
            for i in self.tool[key]:
                c = copy.copy(i)
                doc_url, _ = urlparse.urldefrag(c['id'])
                c["name"] = shortname(c["id"])
                del c["id"]

                if "type" not in c:
                    raise validate.ValidationException("Missing `type` in parameter `%s`" % c["name"])

                if "default" in c and "null" not in aslist(c["type"]):
                    c["type"] = ["null"] + aslist(c["type"])
                else:
                    c["type"] = c["type"]

                if key == "inputs":
                    self.inputs_record_schema["fields"].append(c)
                elif key == "outputs":
                    self.outputs_record_schema["fields"].append(c)

        try:
            self.inputs_record_schema = schema_salad.schema.make_valid_avro(self.inputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.inputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException("Got error `%s` while prcoessing inputs of %s:\n%s" % (str(e), self.tool["id"], json.dumps(self.inputs_record_schema, indent=4)))

        try:
            self.outputs_record_schema = schema_salad.schema.make_valid_avro(self.outputs_record_schema, {}, set())
            avro.schema.make_avsc_object(self.outputs_record_schema, self.names)
        except avro.schema.SchemaParseException as e:
            raise validate.ValidationException("Got error `%s` while prcoessing outputs of %s:\n%s" % (str(e), self.tool["id"], json.dumps(self.outputs_record_schema, indent=4)))


    def _init_job(self, joborder, input_basedir, **kwargs):
        builder = Builder()
        builder.job = copy.deepcopy(joborder)

        for i in self.tool["inputs"]:
            d = shortname(i["id"])
            if d not in builder.job and "default" in i:
                builder.job[d] = i["default"]

        for r in self.requirements:
            if r["class"] not in supportedProcessRequirements:
                raise WorkflowException("Unsupported process requirement %s" % (r["class"]))

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

        dockerReq, _ = self.get_requirement("DockerRequirement")
        if dockerReq and kwargs.get("use_container"):
            builder.outdir = kwargs.get("docker_outdir") or "/tmp/job_output"
            builder.tmpdir = kwargs.get("docker_tmpdir") or "/tmp/job_tmp"
        else:
            builder.outdir = kwargs.get("outdir") or tempfile.mkdtemp()
            builder.tmpdir = kwargs.get("tmpdir") or tempfile.mkdtemp()

        builder.fs_access = kwargs.get("fs_access") or StdFsAccess(input_basedir)

        for i in self.tool["inputs"]:
            d = shortname(i["id"])
            if d in builder.job and i.get("format"):
                checkFormat(builder.job[d], builder.do_eval(i["format"]), self.requirements, self.loader.graph)

        builder.bindings.extend(builder.bind_input(self.inputs_record_schema, builder.job))

        builder.resources = self.evalResources(builder, kwargs)

        return builder

    def evalResources(self, builder, kwargs):
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

    def validate_hints(self, hints, strict):
        for r in hints:
            try:
                if self.names.get_name(r["class"], "") is not None:
                    validate.validate_ex(self.names.get_name(r["class"], ""), r, strict=strict)
                else:
                    _logger.info(validate.ValidationException("Unknown hint %s" % (r["class"])))
            except validate.ValidationException as v:
                raise validate.ValidationException("Validating hint `%s`: %s" % (r["class"], str(v)))

    def get_requirement(self, feature):
        return get_feature(self, feature)

def empty_subtree(dirpath):
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
