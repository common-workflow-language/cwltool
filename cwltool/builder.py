import copy
import logging
import math
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS
from ruamel.yaml.comments import CommentedMap
from schema_salad.avro.schema import Names, Schema, make_avsc_object
from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import SourceLine
from schema_salad.utils import convert_to_dict, json_dumps
from schema_salad.validate import validate
from typing_extensions import TYPE_CHECKING, Type  # pylint: disable=unused-import

from . import expression
from .errors import WorkflowException
from .loghandler import _logger
from .mutation import MutationManager
from .software_requirements import DependenciesConfiguration
from .stdfsaccess import StdFsAccess
from .utils import (
    CONTENT_LIMIT,
    CWLObjectType,
    CWLOutputType,
    aslist,
    docker_windows_path_adjust,
    get_listing,
    normalizeFilesDirs,
    onWindows,
    visit_class,
)

if TYPE_CHECKING:
    from .pathmapper import PathMapper
    from .provenance_profile import ProvenanceProfile  # pylint: disable=unused-import


def content_limit_respected_read_bytes(f):  # type: (IO[bytes]) -> bytes
    contents = f.read(CONTENT_LIMIT + 1)
    if len(contents) > CONTENT_LIMIT:
        raise WorkflowException(
            "file is too large, loadContents limited to %d bytes" % CONTENT_LIMIT
        )
    return contents


def content_limit_respected_read(f):  # type: (IO[bytes]) -> str
    return content_limit_respected_read_bytes(f).decode("utf-8")


def substitute(value, replace):  # type: (str, str) -> str
    if replace.startswith("^"):
        try:
            return substitute(value[0 : value.rindex(".")], replace[1:])
        except ValueError:
            # No extension to remove
            return value + replace.lstrip("^")
    return value + replace


def formatSubclassOf(
    fmt: str, cls: str, ontology: Optional[Graph], visited: Set[str]
) -> bool:
    """Determine if `fmt` is a subclass of `cls`."""
    if URIRef(fmt) == URIRef(cls):
        return True

    if ontology is None:
        return False

    if fmt in visited:
        return False

    visited.add(fmt)

    uriRefFmt = URIRef(fmt)

    for _s, _p, o in ontology.triples((uriRefFmt, RDFS.subClassOf, None)):
        # Find parent classes of `fmt` and search upward
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for _s, _p, o in ontology.triples((uriRefFmt, OWL.equivalentClass, None)):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(o, cls, ontology, visited):
            return True

    for s, _p, _o in ontology.triples((None, OWL.equivalentClass, uriRefFmt)):
        # Find equivalent classes of `fmt` and search horizontally
        if formatSubclassOf(s, cls, ontology, visited):
            return True

    return False


def check_format(
    actual_file: Union[CWLObjectType, List[CWLObjectType]],
    input_formats: Union[List[str], str],
    ontology: Optional[Graph],
) -> None:
    """Confirm that the format present is valid for the allowed formats."""
    for afile in aslist(actual_file):
        if not afile:
            continue
        if "format" not in afile:
            raise ValidationException(
                "File has no 'format' defined: {}".format(json_dumps(afile, indent=4))
            )
        for inpf in aslist(input_formats):
            if afile["format"] == inpf or formatSubclassOf(
                afile["format"], inpf, ontology, set()
            ):
                return
        raise ValidationException(
            "File has an incompatible format: {}".format(json_dumps(afile, indent=4))
        )


class HasReqsHints(object):
    def __init__(self) -> None:
        """Initialize this reqs decorator."""
        self.requirements = []  # type: List[CWLObjectType]
        self.hints = []  # type: List[CWLObjectType]

    def get_requirement(
        self, feature: str
    ) -> Tuple[Optional[CWLObjectType], Optional[bool]]:
        for item in reversed(self.requirements):
            if item["class"] == feature:
                return (item, True)
        for item in reversed(self.hints):
            if item["class"] == feature:
                return (item, False)
        return (None, None)


class Builder(HasReqsHints):
    def __init__(
        self,
        job: CWLObjectType,
        files: List[CWLObjectType],
        bindings: List[CWLObjectType],
        schemaDefs: MutableMapping[str, CWLObjectType],
        names: Names,
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        resources: Dict[str, Union[int, float, str]],
        mutation_manager: Optional[MutationManager],
        formatgraph: Optional[Graph],
        make_fs_access: Type[StdFsAccess],
        fs_access: StdFsAccess,
        job_script_provider: Optional[DependenciesConfiguration],
        timeout: float,
        debug: bool,
        js_console: bool,
        force_docker_pull: bool,
        loadListing: str,
        outdir: str,
        tmpdir: str,
        stagedir: str,
        cwlVersion: str,
    ) -> None:
        """Initialize this Builder."""
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

        self.cwlVersion = cwlVersion

        self.pathmapper = None  # type: Optional[PathMapper]
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.find_default_container = None  # type: Optional[Callable[[], str]]

    def build_job_script(self, commands: List[str]) -> Optional[str]:
        if self.job_script_provider is not None:
            return self.job_script_provider.build_job_script(self, commands)
        return None

    def bind_input(
        self,
        schema: CWLObjectType,
        datum: Union[CWLObjectType, List[CWLObjectType]],
        discover_secondaryFiles: bool,
        lead_pos: Optional[Union[int, List[int]]] = None,
        tail_pos: Optional[Union[str, List[int]]] = None,
    ) -> List[MutableMapping[str, Union[str, List[int]]]]:

        if tail_pos is None:
            tail_pos = []
        if lead_pos is None:
            lead_pos = []

        bindings = []  # type: List[MutableMapping[str, Union[str, List[int]]]]
        binding = (
            {}
        )  # type: Union[MutableMapping[str, Union[str, List[int]]], CommentedMap]
        value_from_expression = False
        if "inputBinding" in schema and isinstance(
            schema["inputBinding"], MutableMapping
        ):
            binding = CommentedMap(schema["inputBinding"].items())

            bp = list(aslist(lead_pos))
            if "position" in binding:
                position = binding["position"]
                if isinstance(position, str):  # no need to test the CWL Version
                    # the schema for v1.0 only allow ints
                    binding["position"] = self.do_eval(position, context=datum)
                    bp.append(binding["position"])
                else:
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
                if isinstance(t, str) and self.names.has_name(t, None):
                    avsc = self.names.get_name(t, None)
                elif (
                    isinstance(t, MutableMapping)
                    and "name" in t
                    and self.names.has_name(cast(str, t["name"]), None)
                ):
                    avsc = self.names.get_name(cast(str, t["name"]), None)
                if not avsc:
                    avsc = make_avsc_object(convert_to_dict(t), self.names)
                if validate(avsc, datum):
                    schema = copy.deepcopy(schema)
                    schema["type"] = t
                    if not value_from_expression:
                        return self.bind_input(
                            schema,
                            datum,
                            lead_pos=lead_pos,
                            tail_pos=tail_pos,
                            discover_secondaryFiles=discover_secondaryFiles,
                        )
                    else:
                        self.bind_input(
                            schema,
                            datum,
                            lead_pos=lead_pos,
                            tail_pos=tail_pos,
                            discover_secondaryFiles=discover_secondaryFiles,
                        )
                        bound_input = True
            if not bound_input:
                raise ValidationException(
                    "'%s' is not a valid union %s" % (datum, schema["type"])
                )
        elif isinstance(schema["type"], MutableMapping):
            st = copy.deepcopy(schema["type"])
            if (
                binding
                and "inputBinding" not in st
                and "type" in st
                and st["type"] == "array"
                and "itemSeparator" not in binding
            ):
                st["inputBinding"] = {}
            for k in ("secondaryFiles", "format", "streamable"):
                if k in schema:
                    st[k] = schema[k]
            if value_from_expression:
                self.bind_input(
                    st,
                    datum,
                    lead_pos=lead_pos,
                    tail_pos=tail_pos,
                    discover_secondaryFiles=discover_secondaryFiles,
                )
            else:
                bindings.extend(
                    self.bind_input(
                        st,
                        datum,
                        lead_pos=lead_pos,
                        tail_pos=tail_pos,
                        discover_secondaryFiles=discover_secondaryFiles,
                    )
                )
        else:
            if schema["type"] in self.schemaDefs:
                schema = self.schemaDefs[cast(str, schema["type"])]

            if schema["type"] == "record":
                datum = cast(CWLObjectType, datum)
                for f in cast(List[CWLObjectType], schema["fields"]):
                    name = cast(str, f["name"])
                    if name in datum and datum[name] is not None:
                        bindings.extend(
                            self.bind_input(
                                f,
                                cast(CWLObjectType, datum[name]),
                                lead_pos=lead_pos,
                                tail_pos=name,
                                discover_secondaryFiles=discover_secondaryFiles,
                            )
                        )
                    else:
                        datum[name] = f.get("default")

            if schema["type"] == "array":
                for n, item in enumerate(cast(MutableSequence[CWLObjectType], datum)):
                    b2 = None
                    if binding:
                        b2 = cast(CWLObjectType, copy.deepcopy(binding))
                        b2["datum"] = item
                    itemschema = {
                        "type": schema["items"],
                        "inputBinding": b2,
                    }  # type: CWLObjectType
                    for k in ("secondaryFiles", "format", "streamable"):
                        if k in schema:
                            itemschema[k] = schema[k]
                    bindings.extend(
                        self.bind_input(
                            itemschema,
                            item,
                            lead_pos=n,
                            tail_pos=tail_pos,
                            discover_secondaryFiles=discover_secondaryFiles,
                        )
                    )
                binding = {}

            def _capture_files(f: CWLObjectType) -> CWLObjectType:
                self.files.append(f)
                return f

            if schema["type"] == "File":
                datum = cast(CWLObjectType, datum)
                self.files.append(datum)

                loadContents_sourceline = (
                    None
                )  # type: Union[None, MutableMapping[str, Union[str, List[int]]], CWLObjectType]
                if binding and binding.get("loadContents"):
                    loadContents_sourceline = binding
                elif schema.get("loadContents"):
                    loadContents_sourceline = schema

                if loadContents_sourceline and loadContents_sourceline["loadContents"]:
                    with SourceLine(
                        loadContents_sourceline, "loadContents", WorkflowException
                    ):
                        try:
                            with self.fs_access.open(
                                cast(str, datum["location"]), "rb"
                            ) as f2:
                                datum["contents"] = content_limit_respected_read(f2)
                        except Exception as e:
                            raise Exception("Reading %s\n%s" % (datum["location"], e))

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                    for sf in aslist(schema["secondaryFiles"]):
                        if "required" in sf:
                            sf_required = self.do_eval(sf["required"], context=datum)
                        else:
                            sf_required = True

                        if "$(" in sf["pattern"] or "${" in sf["pattern"]:
                            sfpath = self.do_eval(sf["pattern"], context=datum)
                        else:
                            sfpath = substitute(
                                cast(str, datum["basename"]), sf["pattern"]
                            )

                        for sfname in aslist(sfpath):
                            if not sfname:
                                continue
                            found = False

                            if isinstance(sfname, str):
                                d_location = cast(str, datum["location"])
                                if "/" in d_location:
                                    sf_location = (
                                        d_location[0 : d_location.rindex("/") + 1]
                                        + sfname
                                    )
                                else:
                                    sf_location = d_location + sfname
                                sfbasename = sfname
                            elif isinstance(sfname, MutableMapping):
                                sf_location = sfname["location"]
                                sfbasename = sfname["basename"]
                            else:
                                raise WorkflowException(
                                    "Expected secondaryFile expression to return type 'str' or 'MutableMapping', received '%s'"
                                    % (type(sfname))
                                )

                            for d in cast(
                                MutableSequence[MutableMapping[str, str]],
                                datum["secondaryFiles"],
                            ):
                                if not d.get("basename"):
                                    d["basename"] = d["location"][
                                        d["location"].rindex("/") + 1 :
                                    ]
                                if d["basename"] == sfbasename:
                                    found = True

                            if not found:

                                def addsf(
                                    files: MutableSequence[CWLObjectType],
                                    newsf: CWLObjectType,
                                ) -> None:
                                    for f in files:
                                        if f["location"] == newsf["location"]:
                                            f["basename"] = newsf["basename"]
                                            return
                                    files.append(newsf)

                                if isinstance(sfname, MutableMapping):
                                    addsf(
                                        cast(
                                            MutableSequence[CWLObjectType],
                                            datum["secondaryFiles"],
                                        ),
                                        sfname,
                                    )
                                elif discover_secondaryFiles and self.fs_access.exists(
                                    sf_location
                                ):
                                    addsf(
                                        cast(
                                            MutableSequence[CWLObjectType],
                                            datum["secondaryFiles"],
                                        ),
                                        {
                                            "location": sf_location,
                                            "basename": sfname,
                                            "class": "File",
                                        },
                                    )
                                elif sf_required:
                                    raise WorkflowException(
                                        "Missing required secondary file '%s' from file object: %s"
                                        % (sfname, json_dumps(datum, indent=4))
                                    )

                    normalizeFilesDirs(
                        cast(MutableSequence[CWLObjectType], datum["secondaryFiles"])
                    )

                if "format" in schema:
                    try:
                        check_format(
                            datum,
                            cast(Union[List[str], str], self.do_eval(schema["format"])),
                            self.formatgraph,
                        )
                    except ValidationException as ve:
                        raise WorkflowException(
                            "Expected value of '%s' to have format %s but\n "
                            " %s" % (schema["name"], schema["format"], ve)
                        ) from ve

                visit_class(
                    datum.get("secondaryFiles", []),
                    ("File", "Directory"),
                    _capture_files,
                )

            if schema["type"] == "Directory":
                datum = cast(CWLObjectType, datum)
                ll = schema.get("loadListing") or self.loadListing
                if ll and ll != "no_listing":
                    get_listing(
                        self.fs_access,
                        datum,
                        (ll == "deep_listing"),
                    )
                self.files.append(datum)

            if schema["type"] == "Any":
                visit_class(datum, ("File", "Directory"), _capture_files)

        # Position to front of the sort key
        if binding:
            for bi in bindings:
                bi["position"] = cast(List[int], binding["position"]) + cast(
                    List[int], bi["position"]
                )
            bindings.append(binding)

        return bindings

    def tostr(self, value: Union[MutableMapping[str, str], Any]) -> str:
        if isinstance(value, MutableMapping) and value.get("class") in (
            "File",
            "Directory",
        ):
            if "path" not in value:
                raise WorkflowException(
                    u'%s object missing "path": %s' % (value["class"], value)
                )

            # Path adjust for windows file path when passing to docker, docker accepts unix like path only
            (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
            if onWindows() and docker_req is not None:
                # docker_req is none only when there is no dockerRequirement
                # mentioned in hints and Requirement
                path = docker_windows_path_adjust(value["path"])
                return path
            return value["path"]
        else:
            return str(value)

    def generate_arg(self, binding: CWLObjectType) -> List[str]:
        value = binding.get("datum")
        if "valueFrom" in binding:
            with SourceLine(
                binding,
                "valueFrom",
                WorkflowException,
                _logger.isEnabledFor(logging.DEBUG),
            ):
                value = self.do_eval(cast(str, binding["valueFrom"]), context=value)

        prefix = cast(Optional[str], binding.get("prefix"))
        sep = binding.get("separate", True)
        if prefix is None and not sep:
            with SourceLine(
                binding,
                "separate",
                WorkflowException,
                _logger.isEnabledFor(logging.DEBUG),
            ):
                raise WorkflowException(
                    "'separate' option can not be specified without prefix"
                )

        argl = []  # type: MutableSequence[CWLOutputType]
        if isinstance(value, MutableSequence):
            if binding.get("itemSeparator") and value:
                itemSeparator = cast(str, binding["itemSeparator"])
                argl = [itemSeparator.join([self.tostr(v) for v in value])]
            elif binding.get("valueFrom"):
                value = [self.tostr(v) for v in value]
                return cast(List[str], ([prefix] if prefix else [])) + cast(
                    List[str], value
                )
            elif prefix and value:
                return [prefix]
            else:
                return []
        elif isinstance(value, MutableMapping) and value.get("class") in (
            "File",
            "Directory",
        ):
            argl = cast(MutableSequence[CWLOutputType], [value])
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
                args.append(self.tostr(j) if prefix is None else prefix + self.tostr(j))

        return [a for a in args if a is not None]

    def do_eval(
        self,
        ex: Optional[CWLOutputType],
        context: Optional[Any] = None,
        recursive: bool = False,
        strip_whitespace: bool = True,
    ) -> Optional[CWLOutputType]:
        if recursive:
            if isinstance(ex, MutableMapping):
                return {k: self.do_eval(v, context, recursive) for k, v in ex.items()}
            if isinstance(ex, MutableSequence):
                return [self.do_eval(v, context, recursive) for v in ex]

        resources = self.resources
        if self.resources and "cores" in self.resources:
            cores = resources["cores"]
            if not isinstance(cores, str):
                resources = copy.copy(resources)
                resources["cores"] = int(math.ceil(cores))

        return expression.do_eval(
            ex,
            self.job,
            self.requirements,
            self.outdir,
            self.tmpdir,
            resources,
            context=context,
            timeout=self.timeout,
            debug=self.debug,
            js_console=self.js_console,
            force_docker_pull=self.force_docker_pull,
            strip_whitespace=strip_whitespace,
            cwlVersion=self.cwlVersion,
        )
