from __future__ import absolute_import
import copy
import os
import logging
from typing import Any, Callable, Dict, List, Text, Type, Union

import six
from six import iteritems, string_types

import avro
import schema_salad.validate as validate
from schema_salad.sourceline import SourceLine

from . import expression
from .errors import WorkflowException
from .mutation import MutationManager
from .pathmapper import (PathMapper, get_listing, normalizeFilesDirs,
                         visit_class)
from .stdfsaccess import StdFsAccess
from .utils import aslist, get_feature, docker_windows_path_adjust, onWindows

_logger = logging.getLogger("cwltool")

AvroSchemaFromJSONData = avro.schema.make_avsc_object

CONTENT_LIMIT = 64 * 1024


def substitute(value, replace):  # type: (Text, Text) -> Text
    if replace[0] == "^":
        return substitute(value[0:value.rindex('.')], replace[1:])
    else:
        return value + replace


class Builder(object):
    def __init__(self):  # type: () -> None
        self.names = None  # type: avro.schema.Names
        self.schemaDefs = None  # type: Dict[Text, Dict[Text, Any]]
        self.files = None  # type: List[Dict[Text, Text]]
        self.fs_access = None  # type: StdFsAccess
        self.job = None  # type: Dict[Text, Union[Dict[Text, Any], List, Text]]
        self.requirements = None  # type: List[Dict[Text, Any]]
        self.hints = None  # type: List[Dict[Text, Any]]
        self.outdir = None  # type: Text
        self.tmpdir = None  # type: Text
        self.resources = None  # type: Dict[Text, Union[int, Text]]
        self.bindings = []  # type: List[Dict[Text, Any]]
        self.timeout = None  # type: int
        self.pathmapper = None  # type: PathMapper
        self.stagedir = None  # type: Text
        self.make_fs_access = None  # type: Type[StdFsAccess]
        self.debug = False  # type: bool
        self.js_console = False  # type: bool
        self.mutation_manager = None  # type: MutationManager
        self.force_docker_pull = False  # type: bool

        # One of "no_listing", "shallow_listing", "deep_listing"
        # Will be default "no_listing" for CWL v1.1
        self.loadListing = "deep_listing"  # type: Union[None, str]

        self.find_default_container = None  # type: Callable[[], Text]
        self.job_script_provider = None  # type: Any

    def build_job_script(self, commands):
        # type: (List[Text]) -> Text
        build_job_script_method = getattr(self.job_script_provider, "build_job_script", None)  # type: Callable[[Builder, Union[List[str],List[Text]]], Text]
        if build_job_script_method:
            return build_job_script_method(self, commands)
        else:
            return None

    def bind_input(self, schema, datum, lead_pos=None, tail_pos=None):
        # type: (Dict[Text, Any], Any, Union[int, List[int]], List[int]) -> List[Dict[Text, Any]]
        if tail_pos is None:
            tail_pos = []
        if lead_pos is None:
            lead_pos = []
        bindings = []  # type: List[Dict[Text,Text]]
        binding = None  # type: Dict[Text,Any]
        value_from_expression = False
        if "inputBinding" in schema and isinstance(schema["inputBinding"], dict):
            binding = copy.copy(schema["inputBinding"])

            if "position" in binding:
                binding["position"] = aslist(lead_pos) + aslist(binding["position"]) + aslist(tail_pos)
            else:
                binding["position"] = aslist(lead_pos) + [0] + aslist(tail_pos)

            binding["datum"] = datum
            if "valueFrom" in binding:
                value_from_expression = True

        # Handle union types
        if isinstance(schema["type"], list):
            if not value_from_expression:
                for t in schema["type"]:
                    if isinstance(t, (str, Text)) and self.names.has_name(t, ""):
                        avsc = self.names.get_name(t, "")
                    elif isinstance(t, dict) and "name" in t and self.names.has_name(t["name"], ""):
                        avsc = self.names.get_name(t["name"], "")
                    else:
                        avsc = AvroSchemaFromJSONData(t, self.names)
                    if validate.validate(avsc, datum):
                        schema = copy.deepcopy(schema)
                        schema["type"] = t
                        return self.bind_input(schema, datum, lead_pos=lead_pos, tail_pos=tail_pos)
                raise validate.ValidationException(u"'%s' is not a valid union %s" % (datum, schema["type"]))
        elif isinstance(schema["type"], dict):
            if not value_from_expression:
                st = copy.deepcopy(schema["type"])
                if binding and "inputBinding" not in st and st["type"] == "array" and "itemSeparator" not in binding:
                    st["inputBinding"] = {}
                for k in ("secondaryFiles", "format", "streamable"):
                    if k in schema:
                        st[k] = schema[k]
                bindings.extend(self.bind_input(st, datum, lead_pos=lead_pos, tail_pos=tail_pos))
        else:
            if schema["type"] in self.schemaDefs:
                schema = self.schemaDefs[schema["type"]]

            if schema["type"] == "record":
                for f in schema["fields"]:
                    if f["name"] in datum:
                        bindings.extend(self.bind_input(f, datum[f["name"]], lead_pos=lead_pos, tail_pos=f["name"]))
                    else:
                        datum[f["name"]] = f.get("default")

            if schema["type"] == "array":
                for n, item in enumerate(datum):
                    b2 = None
                    if binding:
                        b2 = copy.deepcopy(binding)
                        b2["datum"] = item
                    itemschema = {
                        u"type": schema["items"],
                        u"inputBinding": b2
                    }
                    for k in ("secondaryFiles", "format", "streamable"):
                        if k in schema:
                            itemschema[k] = schema[k]
                    bindings.extend(
                        self.bind_input(itemschema, item, lead_pos=n, tail_pos=tail_pos))
                binding = None

            if schema["type"] == "File":
                self.files.append(datum)
                if binding:
                    if binding.get("loadContents"):
                        with self.fs_access.open(datum["location"], "rb") as f:
                            datum["contents"] = f.read(CONTENT_LIMIT)

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                    for sf in aslist(schema["secondaryFiles"]):
                        if isinstance(sf, dict) or "$(" in sf or "${" in sf:
                            sfpath = self.do_eval(sf, context=datum)
                        else:
                            sfpath = substitute(datum["basename"], sf)
                        for sfname in aslist(sfpath):
                            found = False
                            for d in datum["secondaryFiles"]:
                                if not d.get("basename"):
                                    d["basename"] = d["location"][d["location"].rindex("/")+1:]
                                if d["basename"] == sfname:
                                    found = True
                            if not found:
                                if isinstance(sfname, dict):
                                    datum["secondaryFiles"].append(sfname)
                                else:
                                    datum["secondaryFiles"].append({
                                        "location": datum["location"][0:datum["location"].rindex("/")+1]+sfname,
                                        "basename": sfname,
                                        "class": "File"})

                    normalizeFilesDirs(datum["secondaryFiles"])

                def _capture_files(f):
                    self.files.append(f)
                    return f

                visit_class(datum.get("secondaryFiles", []), ("File", "Directory"), _capture_files)

            if schema["type"] == "Directory":
                ll = self.loadListing or (binding and binding.get("loadListing"))
                if ll and ll != "no_listing":
                    get_listing(self.fs_access, datum, (ll == "deep_listing"))
                self.files.append(datum)

        # Position to front of the sort key
        if binding:
            for bi in bindings:
                bi["position"] = binding["position"] + bi["position"]
            bindings.append(binding)

        return bindings

    def tostr(self, value):  # type: (Any) -> Text
        if isinstance(value, dict) and value.get("class") in ("File", "Directory"):
            if "path" not in value:
                raise WorkflowException(u"%s object missing \"path\": %s" % (value["class"], value))

            # Path adjust for windows file path when passing to docker, docker accepts unix like path only
            (docker_req, docker_is_req) = get_feature(self, "DockerRequirement")
            if onWindows() and docker_req is not None:  # docker_req is none only when there is no dockerRequirement mentioned in hints and Requirement
                return docker_windows_path_adjust(value["path"])
            return value["path"]
        else:
            return Text(value)

    def generate_arg(self, binding):  # type: (Dict[Text,Any]) -> List[Text]
        value = binding.get("datum")
        if "valueFrom" in binding:
            with SourceLine(binding, "valueFrom", WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                value = self.do_eval(binding["valueFrom"], context=value)

        prefix = binding.get("prefix")
        sep = binding.get("separate", True)
        if prefix is None and not sep:
            with SourceLine(binding, "separate", WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                raise WorkflowException("'separate' option can not be specified without prefix")

        l = []  # type: List[Dict[Text,Text]]
        if isinstance(value, list):
            if binding.get("itemSeparator") and value:
                l = [binding["itemSeparator"].join([self.tostr(v) for v in value])]
            elif binding.get("valueFrom"):
                value = [self.tostr(v) for v in value]
                return ([prefix] if prefix else []) + value
            elif prefix and value:
                return [prefix]
            else:
                return []
        elif isinstance(value, dict) and value.get("class") in ("File", "Directory"):
            l = [value]
        elif isinstance(value, dict):
            return [prefix] if prefix else []
        elif value is True and prefix:
            return [prefix]
        elif value is False or value is None or (value is True and not prefix):
            return []
        else:
            l = [value]

        args = []
        for j in l:
            if sep:
                args.extend([prefix, self.tostr(j)])
            else:
                args.append(prefix + self.tostr(j))

        return [a for a in args if a is not None]

    def do_eval(self, ex, context=None, pull_image=True, recursive=False, strip_whitespace=True):
        # type: (Union[Dict[Text, Text], Text], Any, bool, bool, bool) -> Any
        if recursive:
            if isinstance(ex, dict):
                return {k: self.do_eval(v, context, pull_image, recursive) for k, v in iteritems(ex)}
            if isinstance(ex, list):
                return [self.do_eval(v, context, pull_image, recursive) for v in ex]
        if context is None and type(ex) is str and "self" in ex:
            return None
        return expression.do_eval(ex, self.job, self.requirements,
                                  self.outdir, self.tmpdir,
                                  self.resources,
                                  context=context, pull_image=pull_image,
                                  timeout=self.timeout,
                                  debug=self.debug,
                                  js_console=self.js_console,
                                  force_docker_pull=self.force_docker_pull,
                                  strip_whitespace=strip_whitespace)
