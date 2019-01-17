from __future__ import absolute_import

import copy
import logging
from typing import (Any, Callable, Dict, List, MutableMapping, MutableSequence,
                    Optional, Set, Tuple, Union)

from rdflib import Graph, URIRef  # pylint: disable=unused-import
from rdflib.namespace import OWL, RDFS
from ruamel.yaml.comments import CommentedMap
from schema_salad import validate
from schema_salad.schema import Names, convert_to_dict
from schema_salad.avro.schema import make_avsc_object, Schema
from schema_salad.sourceline import SourceLine
from six import iteritems, string_types
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text, Type)
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import expression
from .errors import WorkflowException
from .loghandler import _logger
from .mutation import MutationManager  # pylint: disable=unused-import
from .pathmapper import PathMapper  # pylint: disable=unused-import
from .pathmapper import get_listing, normalizeFilesDirs, visit_class
from .stdfsaccess import StdFsAccess  # pylint: disable=unused-import
from .utils import aslist, docker_windows_path_adjust, json_dumps, onWindows



if TYPE_CHECKING:
    from .provenance import ProvenanceProfile  # pylint: disable=unused-import
CONTENT_LIMIT = 64 * 1024


def substitute(value, replace):  # type: (Text, Text) -> Text
    if replace[0] == "^":
        return substitute(value[0:value.rindex('.')], replace[1:])
    return value + replace

def formatSubclassOf(fmt, cls, ontology, visited):
    # type: (Text, Text, Optional[Graph], Set[Text]) -> bool
    """Determine if `fmt` is a subclass of `cls`."""

    if URIRef(fmt) == URIRef(cls):
        return True

    if ontology is None:
        return False

    if fmt in visited:
        return False

    visited.add(fmt)

    uriRefFmt = URIRef(fmt)

    for s, p, o in ontology.triples((uriRefFmt, RDFS.subClassOf, None)):
        # Find parent classes of `fmt` and search upward
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for s, p, o in ontology.triples((uriRefFmt, OWL.equivalentClass, None)):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for s, p, o in ontology.triples((None, OWL.equivalentClass, uriRefFmt)):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(s, cls, ontology, visited):
            return True

    return False

def check_format(actual_file,    # type: Union[Dict[Text, Any], List, Text]
                 input_formats,  # type: Union[List[Text], Text]
                 ontology        # type: Optional[Graph]
                ):  # type: (...) -> None
    """ Confirms that the format present is valid for the allowed formats."""
    for afile in aslist(actual_file):
        if not afile:
            continue
        if "format" not in afile:
            raise validate.ValidationException(
                u"File has no 'format' defined: {}".format(
                    json_dumps(afile, indent=4)))
        for inpf in aslist(input_formats):
            if afile["format"] == inpf or \
                    formatSubclassOf(afile["format"], inpf, ontology, set()):
                return
        raise validate.ValidationException(
            u"File has an incompatible format: {}".format(
                json_dumps(afile, indent=4)))

class HasReqsHints(object):
    def __init__(self):
        self.requirements = []  # List[Dict[Text, Any]]
        self.hints = []         # List[Dict[Text, Any]]

    def get_requirement(self,
                        feature  # type: Text
                       ):  # type: (...) -> Tuple[Optional[Any], Optional[bool]]
        for item in reversed(self.requirements):
            if item["class"] == feature:
                return (item, True)
        for item in reversed(self.hints):
            if item["class"] == feature:
                return (item, False)
        return (None, None)

class Builder(HasReqsHints):
    def __init__(self,
                 job,                  # type: Dict[Text, Union[Dict[Text, Any], List, Text, None]]
                 files,                # type: List[Dict[Text, Text]]
                 bindings,             # type: List[Dict[Text, Any]]
                 schemaDefs,           # type: Dict[Text, Dict[Text, Any]]
                 names,                # type: Names
                 requirements,         # type: List[Dict[Text, Any]]
                 hints,                # type: List[Dict[Text, Any]]
                 resources,            # type: Dict[str, int]
                 mutation_manager,     # type: Optional[MutationManager]
                 formatgraph,          # type: Optional[Graph]
                 make_fs_access,       # type: Type[StdFsAccess]
                 fs_access,            # type: StdFsAccess
                 job_script_provider,  # type: Optional[Any]
                 timeout,              # type: float
                 debug,                # type: bool
                 js_console,           # type: bool
                 force_docker_pull,    # type: bool
                 loadListing,          # type: Text
                 outdir,               # type: Text
                 tmpdir,               # type: Text
                 stagedir,             # type: Text
                ):  # type: (...) -> None

        self.job = job
        self.files = files
        self.bindings = bindings
        self.schemaDefs = schemaDefs
        self.names = names
        self.requirements = requirements
        self.hints = hints
        self.resources = resources
        self.mutation_manager = mutation_manager
        self.formatgraph = formatgraph

        self.make_fs_access = make_fs_access
        self.fs_access = fs_access

        self.job_script_provider = job_script_provider

        self.timeout = timeout

        self.debug = debug
        self.js_console = js_console
        self.force_docker_pull = force_docker_pull

        # One of "no_listing", "shallow_listing", "deep_listing"
        self.loadListing = loadListing

        self.outdir = outdir
        self.tmpdir = tmpdir
        self.stagedir = stagedir

        self.pathmapper = None  # type: Optional[PathMapper]
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.find_default_container = None  # type: Optional[Callable[[], Text]]

    def build_job_script(self, commands):
        # type: (List[Text]) -> Text
        build_job_script_method = getattr(self.job_script_provider, "build_job_script", None)  # type: Callable[[Builder, Union[List[str],List[Text]]], Text]
        if build_job_script_method is not None:
            return build_job_script_method(self, commands)
        return None

    def bind_input(self,
                   schema,                   # type: MutableMapping[Text, Any]
                   datum,                    # type: Any
                   discover_secondaryFiles,  # type: bool
                   lead_pos=None,            # type: Optional[Union[int, List[int]]]
                   tail_pos=None,            # type: Optional[List[int]]
                  ):  # type: (...) -> List[MutableMapping[Text, Any]]

        if tail_pos is None:
            tail_pos = []
        if lead_pos is None:
            lead_pos = []

        bindings = []  # type: List[MutableMapping[Text, Text]]
        binding = None  # type: Optional[MutableMapping[Text,Any]]
        value_from_expression = False
        if "inputBinding" in schema and isinstance(schema["inputBinding"], MutableMapping):
            binding = CommentedMap(schema["inputBinding"].items())
            assert binding is not None

            bp = list(aslist(lead_pos))
            if "position" in binding:
                bp.extend(aslist(binding["position"]))
            else:
                bp.append(0)
            bp.extend(aslist(tail_pos))
            binding["position"] = bp

            binding["datum"] = datum
            if "valueFrom" in binding:
                value_from_expression = True

        # Handle union types
        if isinstance(schema["type"], MutableSequence):
            bound_input = False
            for t in schema["type"]:
                avsc = None  # type: Optional[Schema]
                if isinstance(t, string_types) and self.names.has_name(t, ""):
                    avsc = self.names.get_name(t, "")
                elif isinstance(t, MutableMapping) and "name" in t and self.names.has_name(t["name"], ""):
                    avsc = self.names.get_name(t["name"], "")
                if not avsc:
                    avsc = make_avsc_object(convert_to_dict(t), self.names)
                assert avsc is not None
                if validate.validate(avsc, datum):
                    schema = copy.deepcopy(schema)
                    schema["type"] = t
                    if not value_from_expression:
                        return self.bind_input(schema, datum, lead_pos=lead_pos, tail_pos=tail_pos, discover_secondaryFiles=discover_secondaryFiles)
                    else:
                        self.bind_input(schema, datum, lead_pos=lead_pos, tail_pos=tail_pos, discover_secondaryFiles=discover_secondaryFiles)
                        bound_input = True
            if not bound_input:
                raise validate.ValidationException(u"'%s' is not a valid union %s" % (datum, schema["type"]))
        elif isinstance(schema["type"], MutableMapping):
            st = copy.deepcopy(schema["type"])
            if binding is not None\
                    and "inputBinding" not in st\
                    and "type" in st\
                    and st["type"] == "array"\
                    and "itemSeparator" not in binding:
                st["inputBinding"] = {}
            for k in ("secondaryFiles", "format", "streamable"):
                if k in schema:
                    st[k] = schema[k]
            if value_from_expression:
                self.bind_input(st, datum, lead_pos=lead_pos, tail_pos=tail_pos, discover_secondaryFiles=discover_secondaryFiles)
            else:
                bindings.extend(self.bind_input(st, datum, lead_pos=lead_pos, tail_pos=tail_pos, discover_secondaryFiles=discover_secondaryFiles))
        else:
            if schema["type"] in self.schemaDefs:
                schema = self.schemaDefs[schema["type"]]

            if schema["type"] == "record":
                for f in schema["fields"]:
                    if f["name"] in datum and datum[f["name"]] is not None:
                        bindings.extend(self.bind_input(f, datum[f["name"]], lead_pos=lead_pos, tail_pos=f["name"], discover_secondaryFiles=discover_secondaryFiles))
                    else:
                        datum[f["name"]] = f.get("default")

            if schema["type"] == "array":
                for n, item in enumerate(datum):
                    b2 = None
                    if binding is not None:
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
                        self.bind_input(itemschema, item, lead_pos=n, tail_pos=tail_pos, discover_secondaryFiles=discover_secondaryFiles))
                binding = None

            def _capture_files(f):
                self.files.append(f)
                return f

            if schema["type"] == "File":
                self.files.append(datum)
                if (binding and binding.get("loadContents")) or schema.get("loadContents"):
                    with self.fs_access.open(datum["location"], "rb") as f:
                        datum["contents"] = f.read(CONTENT_LIMIT).decode("utf-8")

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                    for sf in aslist(schema["secondaryFiles"]):
                        if isinstance(sf, MutableMapping) or "$(" in sf or "${" in sf:
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
                                if isinstance(sfname, MutableMapping):
                                    datum["secondaryFiles"].append(sfname)
                                elif discover_secondaryFiles:
                                    datum["secondaryFiles"].append({
                                        "location": datum["location"][0:datum["location"].rindex("/")+1]+sfname,
                                        "basename": sfname,
                                        "class": "File"})
                                else:
                                    raise WorkflowException("Missing required secondary file '%s' from file object: %s" % (
                                        sfname, json_dumps(datum, indent=4)))

                    normalizeFilesDirs(datum["secondaryFiles"])

                if "format" in schema:
                    try:
                        check_format(datum, self.do_eval(schema["format"]),
                                     self.formatgraph)
                    except validate.ValidationException as ve:
                        raise WorkflowException(
                            "Expected value of '%s' to have format %s but\n "
                            " %s" % (schema["name"], schema["format"], ve))

                visit_class(datum.get("secondaryFiles", []), ("File", "Directory"), _capture_files)

            if schema["type"] == "Directory":
                ll = self.loadListing or (binding and binding.get("loadListing"))
                if ll and ll != "no_listing":
                    get_listing(self.fs_access, datum, (ll == "deep_listing"))
                self.files.append(datum)

            if schema["type"] == "Any":
                visit_class(datum, ("File", "Directory"), _capture_files)

        # Position to front of the sort key
        if binding is not None:
            for bi in bindings:
                bi["position"] = binding["position"] + bi["position"]
            bindings.append(binding)

        return bindings

    def tostr(self, value):  # type: (Any) -> Text
        if isinstance(value, MutableMapping) and value.get("class") in ("File", "Directory"):
            if "path" not in value:
                raise WorkflowException(u"%s object missing \"path\": %s" % (value["class"], value))

            # Path adjust for windows file path when passing to docker, docker accepts unix like path only
            (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
            if onWindows() and docker_req is not None:
                # docker_req is none only when there is no dockerRequirement
                # mentioned in hints and Requirement
                path = docker_windows_path_adjust(value["path"])
                assert path is not None
                return path
            return value["path"]
        else:
            return Text(value)

    def generate_arg(self, binding):  # type: (Dict[Text, Any]) -> List[Text]
        value = binding.get("datum")
        if "valueFrom" in binding:
            with SourceLine(binding, "valueFrom", WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                value = self.do_eval(binding["valueFrom"], context=value)

        prefix = binding.get("prefix")  # type: Optional[Text]
        sep = binding.get("separate", True)
        if prefix is None and not sep:
            with SourceLine(binding, "separate", WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                raise WorkflowException("'separate' option can not be specified without prefix")

        argl = []  # type: MutableSequence[MutableMapping[Text, Text]]
        if isinstance(value, MutableSequence):
            if binding.get("itemSeparator") and value:
                argl = [binding["itemSeparator"].join([self.tostr(v) for v in value])]
            elif binding.get("valueFrom"):
                value = [self.tostr(v) for v in value]
                return ([prefix] if prefix else []) + value
            elif prefix and value:
                return [prefix]
            else:
                return []
        elif isinstance(value, MutableMapping) and value.get("class") in ("File", "Directory"):
            argl = [value]
        elif isinstance(value, MutableMapping):
            return [prefix] if prefix else []
        elif value is True and prefix:
            return [prefix]
        elif value is False or value is None or (value is True and not prefix):
            return []
        else:
            argl = [value]

        args = []
        for j in argl:
            if sep:
                args.extend([prefix, self.tostr(j)])
            else:
                assert prefix is not None
                args.append(prefix + self.tostr(j))

        return [a for a in args if a is not None]

    def do_eval(self, ex, context=None, recursive=False, strip_whitespace=True):
        # type: (Union[Dict[Text, Text], Text], Any, bool, bool) -> Any
        if recursive:
            if isinstance(ex, MutableMapping):
                return {k: self.do_eval(v, context, recursive)
                        for k, v in iteritems(ex)}
            if isinstance(ex, MutableSequence):
                return [self.do_eval(v, context, recursive)
                        for v in ex]

        return expression.do_eval(ex, self.job, self.requirements,
                                  self.outdir, self.tmpdir,
                                  self.resources,
                                  context=context,
                                  timeout=self.timeout,
                                  debug=self.debug,
                                  js_console=self.js_console,
                                  force_docker_pull=self.force_docker_pull,
                                  strip_whitespace=strip_whitespace)
