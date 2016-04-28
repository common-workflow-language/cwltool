import copy
from .utils import aslist
from . import expression
import avro
import schema_salad.validate as validate
from typing import Any, Union, AnyStr, Callable
from .errors import WorkflowException
from .stdfsaccess import StdFsAccess
from .pathmapper import PathMapper

CONTENT_LIMIT = 64 * 1024


def substitute(value, replace):  # type: (str, str) -> str
    if replace[0] == "^":
        return substitute(value[0:value.rindex('.')], replace[1:])
    else:
        return value + replace

def adjustFileObjs(rec, op):  # type: (Any, Callable[[Any], Any]) -> None
    """Apply an update function to each File object in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            op(rec)
        for d in rec:
            adjustFileObjs(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFileObjs(d, op)

class Builder(object):

    def __init__(self):  # type: () -> None
        self.names = None  # type: avro.schema.Names
        self.schemaDefs = None  # type: Dict[str,Dict[unicode, Any]]
        self.files = None  # type: List[Dict[str, str]]
        self.fs_access = None  # type: StdFsAccess
        self.job = None  # type: Dict[str, Any]
        self.requirements = None  # type: List[Dict[str,Any]]
        self.outdir = None  # type: str
        self.tmpdir = None  # type: str
        self.resources = None  # type: Dict[str, Union[int, str]]
        self.bindings = []  # type: List[Dict[str, Any]]
        self.timeout = None  # type: int
        self.pathmapper = None # type: PathMapper

    def bind_input(self, schema, datum, lead_pos=[], tail_pos=[]):
        # type: (Dict[unicode, Any], Any, List[int], List[int]) -> List[Dict[str, Any]]
        bindings = []  # type: List[Dict[str,str]]
        binding = None  # type: Dict[str,Any]
        if "inputBinding" in schema and isinstance(schema["inputBinding"], dict):
            binding = copy.copy(schema["inputBinding"])

            if "position" in binding:
                binding["position"] = aslist(lead_pos) + aslist(binding["position"]) + aslist(tail_pos)
            else:
                binding["position"] = aslist(lead_pos) + [0] + aslist(tail_pos)

            if "valueFrom" in binding:
                binding["do_eval"] = binding["valueFrom"]
            binding["valueFrom"] = datum

        # Handle union types
        if isinstance(schema["type"], list):
            for t in schema["type"]:
                if isinstance(t, (str, unicode)) and self.names.has_name(t, ""):
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
            if binding and "inputBinding" not in st and "itemSeparator" not in binding and st["type"] in ("array", "map"):
                st["inputBinding"] = {}
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

            if schema["type"] == "map":
                for n, item in datum.items():
                    b2 = None
                    if binding:
                        b2 = copy.deepcopy(binding)
                        b2["valueFrom"] = [n, item]
                    bindings.extend(self.bind_input({"type": schema["values"], "inputBinding": b2},
                                                    item, lead_pos=n, tail_pos=tail_pos))
                binding = None

            if schema["type"] == "array":
                for n, item in enumerate(datum):
                    b2 = None
                    if binding:
                        b2 = copy.deepcopy(binding)
                        b2["valueFrom"] = item
                    bindings.extend(self.bind_input({"type": schema["items"], "inputBinding": b2},
                                                    item, lead_pos=n, tail_pos=tail_pos))
                binding = None

            if schema["type"] == "File":
                self.files.append(datum)
                if binding and binding.get("loadContents"):
                    with self.fs_access.open(datum["path"], "rb") as f:
                        datum["contents"] = f.read(CONTENT_LIMIT)

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                    for sf in aslist(schema["secondaryFiles"]):
                        if isinstance(sf, dict) or "$(" in sf or "${" in sf:
                            secondary_eval = self.do_eval(sf, context=datum)
                            if isinstance(secondary_eval, basestring):
                                sfpath = {"path": secondary_eval, "class": "File"}
                            else:
                                sfpath = secondary_eval
                        else:
                            sfpath = {"path": substitute(datum["path"], sf), "class": "File"}
                        if isinstance(sfpath, list):
                            datum["secondaryFiles"].extend(sfpath)
                        else:
                            datum["secondaryFiles"].append(sfpath)

                def _capture_files(f):
                    self.files.append(f)
                    return f

                adjustFileObjs(datum.get("secondaryFiles", []), _capture_files)

        # Position to front of the sort key
        if binding:
            for bi in bindings:
                bi["position"] = binding["position"] + bi["position"]
            bindings.append(binding)

        return bindings

    def tostr(self, value):  # type: (Any) -> str
        if isinstance(value, dict) and value.get("class") == "File":
            if "path" not in value:
                raise WorkflowException(u"File object must have \"path\": %s" % (value))
            return value["path"]
        else:
            return str(value)

    def generate_arg(self, binding):  # type: (Dict[str,Any]) -> List[str]
        value = binding["valueFrom"]
        if "do_eval" in binding:
            value = self.do_eval(binding["do_eval"], context=value)

        prefix = binding.get("prefix")
        sep = binding.get("separate", True)

        l = []  # type: List[Dict[str,str]]
        if isinstance(value, list):
            if binding.get("itemSeparator"):
                l = [binding["itemSeparator"].join([self.tostr(v) for v in value])]
            elif binding.get("do_eval"):
                value = [v["path"] if isinstance(v, dict) and v.get("class") == "File" else v for v in value]
                return ([prefix] if prefix else []) + value
            elif prefix:
                return [prefix]
            else:
                return []
        elif isinstance(value, dict) and value.get("class") == "File":
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

    def do_eval(self, ex, context=None, pull_image=True):
        # type: (Dict[str,str], Any, bool) -> Any
        return expression.do_eval(ex, self.job, self.requirements,
                                  self.outdir, self.tmpdir,
                                  self.resources,
                                  context=context, pull_image=pull_image,
                                  timeout=self.timeout)
