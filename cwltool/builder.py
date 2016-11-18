import copy
from .utils import aslist
from . import expression
import avro
import schema_salad.validate as validate
from schema_salad.sourceline import SourceLine
from typing import Any, Callable, Text, Type, Union
from .errors import WorkflowException
from .stdfsaccess import StdFsAccess
from .pathmapper import PathMapper, adjustFileObjs, adjustDirObjs, normalizeFilesDirs

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
        self.build_job_script = None  # type: Callable[[List[str]], Text]
        self.debug = False  # type: bool

    def bind_input(self, schema, datum, lead_pos=[], tail_pos=[]):
        # type: (Dict[Text, Any], Any, Union[int, List[int]], List[int]) -> List[Dict[Text, Any]]
        bindings = []  # type: List[Dict[Text,Text]]
        binding = None  # type: Dict[Text,Any]
        if "inputBinding" in schema and isinstance(schema["inputBinding"], dict):
            binding = copy.copy(schema["inputBinding"])

            if "position" in binding:
                binding["position"] = aslist(lead_pos) + aslist(binding["position"]) + aslist(tail_pos)
            else:
                binding["position"] = aslist(lead_pos) + [0] + aslist(tail_pos)

            binding["datum"] = datum

        # Handle union types
        if isinstance(schema["type"], list):
            for t in schema["type"]:
                if isinstance(t, (str, Text)) and self.names.has_name(t, ""):
                    avsc = self.names.get_name(t, "")
                elif isinstance(t, dict) and "name" in t and self.names.has_name(t["name"], ""):
                    avsc = self.names.get_name(t["name"], "")
                else:
                    avsc = avro.schema.make_avsc_object(t, self.names)
                if validate.validate(avsc, datum):
                    schema = copy.deepcopy(schema)
                    schema["type"] = t
                    return self.bind_input(schema, datum, lead_pos=lead_pos, tail_pos=tail_pos)
            raise validate.ValidationException(u"'%s' is not a valid union %s" % (datum, schema["type"]))
        elif isinstance(schema["type"], dict):
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
                if binding and binding.get("loadContents"):
                    with self.fs_access.open(datum["location"], "rb") as f:
                        datum["contents"] = f.read(CONTENT_LIMIT)

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                    for sf in aslist(schema["secondaryFiles"]):
                        if isinstance(sf, dict) or "$(" in sf or "${" in sf:
                            secondary_eval = self.do_eval(sf, context=datum)
                            if isinstance(secondary_eval, basestring):
                                sfpath = {"location": secondary_eval,
                                          "class": "File"}
                            else:
                                sfpath = secondary_eval
                        else:
                            sfpath = {"location": substitute(datum["location"], sf), "class": "File"}
                        if isinstance(sfpath, list):
                            datum["secondaryFiles"].extend(sfpath)
                        else:
                            datum["secondaryFiles"].append(sfpath)
                    normalizeFilesDirs(datum["secondaryFiles"])

                def _capture_files(f):
                    self.files.append(f)
                    return f

                adjustFileObjs(datum.get("secondaryFiles", []), _capture_files)

            if schema["type"] == "Directory":
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
            return value["path"]
        else:
            return Text(value)

    def generate_arg(self, binding):  # type: (Dict[Text,Any]) -> List[Text]
        value = binding.get("datum")
        if "valueFrom" in binding:
            with SourceLine(binding, "valueFrom", WorkflowException):
                value = self.do_eval(binding["valueFrom"], context=value)

        prefix = binding.get("prefix")
        sep = binding.get("separate", True)

        l = []  # type: List[Dict[Text,Text]]
        if isinstance(value, list):
            if binding.get("itemSeparator"):
                l = [binding["itemSeparator"].join([self.tostr(v) for v in value])]
            elif binding.get("valueFrom"):
                value = [self.tostr(v) for v in value]
                return ([prefix] if prefix else []) + value
            elif prefix:
                return [prefix]
            else:
                return []
        elif isinstance(value, dict) and value.get("class") in ("File", "Directory"):
            l = [value]
        elif isinstance(value, dict):
            return [prefix] if prefix else []
        elif value is True and prefix:
            return [prefix]
        elif value is False or value is None:
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

    def do_eval(self, ex, context=None, pull_image=True, recursive=False):
        # type: (Union[Dict[Text, Text], Text], Any, bool, bool) -> Any
        if recursive:
            if isinstance(ex, dict):
                return {k: self.do_eval(v, context, pull_image, recursive) for k,v in ex.iteritems()}
            if isinstance(ex, list):
                return [self.do_eval(v, context, pull_image, recursive) for v in ex]

        return expression.do_eval(ex, self.job, self.requirements,
                                  self.outdir, self.tmpdir,
                                  self.resources,
                                  context=context, pull_image=pull_image,
                                  timeout=self.timeout,
                                  debug=self.debug)
