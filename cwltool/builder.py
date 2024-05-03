"""Command line builder."""

import copy
import logging
import math
from decimal import Decimal
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Type,
    Union,
    cast,
)

from cwl_utils import expression
from cwl_utils.file_formats import check_format
from mypy_extensions import mypyc_attr
from rdflib import Graph
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.representer import RoundTripRepresenter
from ruamel.yaml.scalarfloat import ScalarFloat
from schema_salad.avro.schema import Names, Schema, make_avsc_object
from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import SourceLine
from schema_salad.utils import convert_to_dict, json_dumps
from schema_salad.validate import validate

from .errors import WorkflowException
from .loghandler import _logger
from .mutation import MutationManager
from .software_requirements import DependenciesConfiguration
from .stdfsaccess import StdFsAccess
from .utils import (
    CONTENT_LIMIT,
    CWLObjectType,
    CWLOutputType,
    HasReqsHints,
    LoadListingType,
    aslist,
    get_listing,
    normalizeFilesDirs,
    visit_class,
)

if TYPE_CHECKING:
    from .cwlprov.provenance_profile import (
        ProvenanceProfile,  # pylint: disable=unused-import
    )
    from .pathmapper import PathMapper

INPUT_OBJ_VOCAB: Dict[str, str] = {
    "Any": "https://w3id.org/cwl/salad#Any",
    "File": "https://w3id.org/cwl/cwl#File",
    "Directory": "https://w3id.org/cwl/cwl#Directory",
}


def content_limit_respected_read_bytes(f: IO[bytes]) -> bytes:
    """
    Read a file as bytes, respecting the :py:data:`~cwltool.utils.CONTENT_LIMIT`.

    :param f: file handle
    :returns: the file contents
    :raises WorkflowException: if the file is too large
    """
    contents = f.read(CONTENT_LIMIT + 1)
    if len(contents) > CONTENT_LIMIT:
        raise WorkflowException(
            "file is too large, loadContents limited to %d bytes" % CONTENT_LIMIT
        )
    return contents


def content_limit_respected_read(f: IO[bytes]) -> str:
    """
    Read a file as a string, respecting the :py:data:`~cwltool.utils.CONTENT_LIMIT`.

    :param f: file handle
    :returns: the file contents
    :raises WorkflowException: if the file is too large
    """
    return str(content_limit_respected_read_bytes(f), "utf-8")


def substitute(value: str, replace: str) -> str:
    """Perform CWL SecondaryFilesDSL style substitution."""
    if replace.startswith("^"):
        try:
            return substitute(value[0 : value.rindex(".")], replace[1:])
        except ValueError:
            # No extension to remove
            return value + replace.lstrip("^")
    return value + replace


@mypyc_attr(allow_interpreted_subclasses=True)
class Builder(HasReqsHints):
    """Helper class to construct a command line from a CWL CommandLineTool."""

    def __init__(
        self,
        job: CWLObjectType,
        files: List[CWLObjectType],
        bindings: List[CWLObjectType],
        schemaDefs: MutableMapping[str, CWLObjectType],
        names: Names,
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        resources: Dict[str, Union[int, float]],
        mutation_manager: Optional[MutationManager],
        formatgraph: Optional[Graph],
        make_fs_access: Type[StdFsAccess],
        fs_access: StdFsAccess,
        job_script_provider: Optional[DependenciesConfiguration],
        timeout: float,
        debug: bool,
        js_console: bool,
        force_docker_pull: bool,
        loadListing: LoadListingType,
        outdir: str,
        tmpdir: str,
        stagedir: str,
        cwlVersion: str,
        container_engine: str,
    ) -> None:
        """
        Initialize this Builder.

        :param timeout: Maximum number of seconds to wait while evaluating CWL
                        expressions.
        """
        super().__init__()
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

        self.loadListing = loadListing

        self.outdir = outdir
        self.tmpdir = tmpdir
        self.stagedir = stagedir

        self.cwlVersion = cwlVersion

        self.pathmapper: Optional["PathMapper"] = None
        self.prov_obj: Optional["ProvenanceProfile"] = None
        self.find_default_container: Optional[Callable[[], str]] = None
        self.container_engine = container_engine

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
        """
        Bind an input object to the command line.

        :raises ValidationException: in the event of an invalid type union
        :raises WorkflowException: if a CWL Expression ("position", "required",
          "pattern", "format") evaluates to the wrong type or if a required
          secondary file is missing
        """
        debug = _logger.isEnabledFor(logging.DEBUG)

        if tail_pos is None:
            tail_pos = []
        if lead_pos is None:
            lead_pos = []

        bindings: List[MutableMapping[str, Union[str, List[int]]]] = []
        binding: Union[MutableMapping[str, Union[str, List[int]]], CommentedMap] = {}
        value_from_expression = False
        if "inputBinding" in schema and isinstance(schema["inputBinding"], MutableMapping):
            binding = CommentedMap(schema["inputBinding"].items())

            bp = list(aslist(lead_pos))
            if "position" in binding:
                position = binding["position"]
                if isinstance(position, str):  # no need to test the CWL Version
                    # the schema for v1.0 only allow ints
                    result = self.do_eval(position, context=datum)
                    if not isinstance(result, int):
                        raise SourceLine(
                            schema["inputBinding"], "position", WorkflowException, debug
                        ).makeError(
                            "'position' expressions must evaluate to an int, "
                            f"not a {type(result)}. Expression {position} "
                            f"resulted in {result!r}."
                        )
                    binding["position"] = result
                    bp.append(result)
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
                avsc: Optional[Schema] = None
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
                if validate(avsc, datum, vocab=INPUT_OBJ_VOCAB):
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
                    "'{}' is not a valid union {}".format(datum, schema["type"])
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
            if schema["type"] == "org.w3id.cwl.salad.Any":
                if isinstance(datum, dict):
                    if datum.get("class") == "File":
                        schema["type"] = "org.w3id.cwl.cwl.File"
                    elif datum.get("class") == "Directory":
                        schema["type"] = "org.w3id.cwl.cwl.Directory"
                    else:
                        schema["type"] = "record"
                        schema["fields"] = [
                            {"name": field_name, "type": "Any"} for field_name in datum.keys()
                        ]
                elif isinstance(datum, list):
                    schema["type"] = "array"
                    schema["items"] = "Any"

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
                    itemschema: CWLObjectType = {
                        "type": schema["items"],
                        "inputBinding": b2,
                    }
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

            if schema["type"] == "org.w3id.cwl.cwl.File":
                datum = cast(CWLObjectType, datum)
                self.files.append(datum)

                loadContents_sourceline: Union[
                    None, MutableMapping[str, Union[str, List[int]]], CWLObjectType
                ] = None
                if binding and binding.get("loadContents"):
                    loadContents_sourceline = binding
                elif schema.get("loadContents"):
                    loadContents_sourceline = schema

                if loadContents_sourceline and loadContents_sourceline["loadContents"]:
                    with SourceLine(
                        loadContents_sourceline,
                        "loadContents",
                        WorkflowException,
                        debug,
                    ):
                        try:
                            with self.fs_access.open(cast(str, datum["location"]), "rb") as f2:
                                datum["contents"] = content_limit_respected_read(f2)
                        except Exception as e:
                            raise Exception("Reading {}\n{}".format(datum["location"], e)) from e

                if "secondaryFiles" in schema:
                    if "secondaryFiles" not in datum:
                        datum["secondaryFiles"] = []
                        sf_schema = aslist(schema["secondaryFiles"])
                    elif not discover_secondaryFiles:
                        sf_schema = []  # trust the inputs
                    else:
                        sf_schema = aslist(schema["secondaryFiles"])

                    for num, sf_entry in enumerate(sf_schema):
                        if "required" in sf_entry and sf_entry["required"] is not None:
                            required_result = self.do_eval(sf_entry["required"], context=datum)
                            if not (isinstance(required_result, bool) or required_result is None):
                                if sf_schema == schema["secondaryFiles"]:
                                    sf_item: Any = sf_schema[num]
                                else:
                                    sf_item = sf_schema
                                raise SourceLine(
                                    sf_item, "required", WorkflowException, debug
                                ).makeError(
                                    "The result of a expression in the field "
                                    "'required' must "
                                    f"be a bool or None, not a {type(required_result)}. "
                                    f"Expression {sf_entry['required']!r} resulted "
                                    f"in {required_result!r}."
                                )
                            sf_required = required_result
                        else:
                            sf_required = True

                        if "$(" in sf_entry["pattern"] or "${" in sf_entry["pattern"]:
                            sfpath = self.do_eval(sf_entry["pattern"], context=datum)
                        else:
                            sfpath = substitute(cast(str, datum["basename"]), sf_entry["pattern"])

                        for sfname in aslist(sfpath):
                            if not sfname:
                                continue
                            found = False

                            if isinstance(sfname, str):
                                d_location = cast(str, datum["location"])
                                if "/" in d_location:
                                    sf_location = (
                                        d_location[0 : d_location.rindex("/") + 1] + sfname
                                    )
                                else:
                                    sf_location = d_location + sfname
                                sfbasename = sfname
                            elif isinstance(sfname, MutableMapping):
                                sf_location = sfname["location"]
                                sfbasename = sfname["basename"]
                            else:
                                raise SourceLine(
                                    sf_entry, "pattern", WorkflowException, debug
                                ).makeError(
                                    "Expected secondaryFile expression to "
                                    "return type 'str', a 'File' or 'Directory' "
                                    "dictionary, or a list of the same. Received "
                                    f"{type(sfname)!r} from {sf_entry['pattern']!r}."
                                )

                            for d in cast(
                                MutableSequence[MutableMapping[str, str]],
                                datum["secondaryFiles"],
                            ):
                                if not d.get("basename"):
                                    d["basename"] = d["location"][d["location"].rindex("/") + 1 :]
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
                                elif discover_secondaryFiles and self.fs_access.exists(sf_location):
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
                                    raise SourceLine(
                                        schema,
                                        "secondaryFiles",
                                        WorkflowException,
                                        debug,
                                    ).makeError(
                                        "Missing required secondary file '%s' from file object: %s"
                                        % (sfname, json_dumps(datum, indent=4))
                                    )

                    normalizeFilesDirs(
                        cast(MutableSequence[CWLObjectType], datum["secondaryFiles"])
                    )

                if "format" in schema:
                    eval_format: Any = self.do_eval(schema["format"])
                    if isinstance(eval_format, str):
                        evaluated_format: Union[str, List[str]] = eval_format
                    elif isinstance(eval_format, MutableSequence):
                        for index, entry in enumerate(eval_format):
                            message = None
                            if not isinstance(entry, str):
                                message = (
                                    "An expression in the 'format' field must "
                                    "evaluate to a string, or list of strings. "
                                    "However a non-string item was received: "
                                    f"{entry!r} of type {type(entry)!r}. "
                                    f"The expression was {schema['format']!r} and "
                                    f"its fully evaluated result is {eval_format!r}."
                                )
                            if expression.needs_parsing(entry):
                                message = (
                                    "For inputs, 'format' field can either "
                                    "contain a single CWL Expression or CWL Parameter "
                                    "Reference, a single format string, or a list of "
                                    "format strings. But the list cannot contain CWL "
                                    "Expressions or CWL Parameter References. List "
                                    f"entry number {index + 1} contains the following "
                                    "unallowed CWL Parameter Reference or Expression: "
                                    f"{entry!r}."
                                )
                            if message:
                                raise SourceLine(
                                    schema["format"], index, WorkflowException, debug
                                ).makeError(message)
                        evaluated_format = cast(List[str], eval_format)
                    else:
                        raise SourceLine(schema, "format", WorkflowException, debug).makeError(
                            "An expression in the 'format' field must "
                            "evaluate to a string, or list of strings. "
                            "However the type of the expression result was "
                            f"{type(eval_format)}. "
                            f"The expression was {schema['format']!r} and "
                            f"its fully evaluated result is {eval_format!r}."
                        )
                    try:
                        check_format(
                            datum,
                            evaluated_format,
                            self.formatgraph,
                        )
                    except ValidationException as ve:
                        raise WorkflowException(
                            f"Expected value of {schema['name']!r} to have "
                            f"format {schema['format']!r} but\n {ve}"
                        ) from ve

                visit_class(
                    datum.get("secondaryFiles", []),
                    ("File", "Directory"),
                    _capture_files,
                )

            if schema["type"] == "org.w3id.cwl.cwl.Directory":
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
        """
        Represent an input parameter as a string.

        :raises WorkflowException: if the item is a File or Directory and the
          "path" is missing.
        """
        if isinstance(value, MutableMapping) and value.get("class") in (
            "File",
            "Directory",
        ):
            if "path" not in value:
                raise WorkflowException(
                    '{} object missing "path": {}'.format(value["class"], value)
                )
            return value["path"]
        elif isinstance(value, ScalarFloat):
            rep = RoundTripRepresenter()
            dec_value = Decimal(rep.represent_scalar_float(value).value)
            if "E" in str(dec_value):
                return str(dec_value.quantize(1))
            return str(dec_value)
        else:
            return str(value)

    def generate_arg(self, binding: CWLObjectType) -> List[str]:
        value = binding.get("datum")
        debug = _logger.isEnabledFor(logging.DEBUG)
        if "valueFrom" in binding:
            with SourceLine(
                binding,
                "valueFrom",
                WorkflowException,
                debug,
            ):
                value = self.do_eval(cast(str, binding["valueFrom"]), context=value)

        prefix = cast(Optional[str], binding.get("prefix"))
        sep = binding.get("separate", True)
        if prefix is None and not sep:
            with SourceLine(
                binding,
                "separate",
                WorkflowException,
                debug,
            ):
                raise WorkflowException("'separate' option can not be specified without prefix")

        argl: MutableSequence[CWLOutputType] = []
        if isinstance(value, MutableSequence):
            if binding.get("itemSeparator") and value:
                itemSeparator = cast(str, binding["itemSeparator"])
                argl = [itemSeparator.join([self.tostr(v) for v in value])]
            elif binding.get("valueFrom"):
                value = [self.tostr(v) for v in value]
                return cast(List[str], ([prefix] if prefix else [])) + cast(List[str], value)
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
            container_engine=self.container_engine,
        )
