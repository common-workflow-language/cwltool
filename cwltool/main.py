#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""Entry point for cwltool."""

import argparse
import functools
import io
import logging
import os
import signal
import sys
import time
import urllib
from codecs import StreamWriter, getwriter
from collections.abc import MutableMapping, MutableSequence
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sized,
    TextIO,
    Tuple,
    Union,
    cast,
)

import argcomplete
import coloredlogs
import pkg_resources  # part of setuptools
from ruamel import yaml
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import (
    ContextType,
    FetcherCallableType,
    Loader,
    file_uri,
    uri_file_path,
)
from schema_salad.sourceline import strip_dup_lineno
from schema_salad.utils import json_dumps

from . import command_line_tool, workflow
from .argparser import arg_parser, generate_parser, get_default_args
from .builder import HasReqsHints
from .context import LoadingContext, RuntimeContext, getdefault
from .cwlrdf import printdot, printrdf
from .errors import UnsupportedRequirement, WorkflowException
from .executors import JobExecutor, MultithreadedJobExecutor, SingleJobExecutor
from .load_tool import (
    default_loader,
    fetch_document,
    jobloaderctx,
    load_overrides,
    make_tool,
    resolve_and_validate_document,
    resolve_overrides,
    resolve_tool_uri,
)
from .loghandler import _logger, defaultStreamHandler
from .mpi import MpiConfig
from .mutation import MutationManager
from .pack import pack
from .process import (
    CWL_IANA,
    Process,
    add_sizes,
    scandeps,
    shortname,
    use_custom_schema,
    use_standard_schema,
)
from .procgenerator import ProcessGenerator
from .provenance import ResearchObject
from .resolver import ga4gh_tool_registries, tool_resolver
from .secrets import SecretStore
from .software_requirements import (
    DependenciesConfiguration,
    get_container_from_software_requirements,
)
from .stdfsaccess import StdFsAccess
from .subgraph import get_subgraph
from .update import ALLUPDATES, UPDATES
from .utils import (
    DEFAULT_TMP_PREFIX,
    CWLObjectType,
    CWLOutputAtomType,
    CWLOutputType,
    adjustDirObjs,
    normalizeFilesDirs,
    onWindows,
    processes_to_kill,
    trim_listing,
    versionstring,
    visit_class,
    windows_default_container_id,
)
from .workflow import Workflow


def _terminate_processes() -> None:
    """Kill all spawned processes.

    Processes to be killed must be appended to `utils.processes_to_kill`
    as they are spawned.

    An important caveat: since there's no supported way to kill another
    thread in Python, this function cannot stop other threads from
    continuing to execute while it kills the processes that they've
    spawned. This may occasionally lead to unexpected behaviour.
    """
    # It's possible that another thread will spawn a new task while
    # we're executing, so it's not safe to use a for loop here.
    while processes_to_kill:
        processes_to_kill.popleft().kill()


def _signal_handler(signum: int, _: Any) -> None:
    """Kill all spawned processes and exit.

    Note that it's possible for another thread to spawn a process after
    all processes have been killed, but before Python exits.

    Refer to the docstring for _terminate_processes() for other caveats.
    """
    _terminate_processes()
    sys.exit(signum)


def generate_example_input(
    inptype: Optional[CWLOutputType],
    default: Optional[CWLOutputType],
) -> Tuple[Any, str]:
    """Convert a single input schema into an example."""
    example = None
    comment = ""
    defaults = {
        "null": "null",
        "Any": "null",
        "boolean": False,
        "int": 0,
        "long": 0,
        "float": 0.1,
        "double": 0.1,
        "string": "a_string",
        "File": yaml.comments.CommentedMap(
            [("class", "File"), ("path", "a/file/path")]
        ),
        "Directory": yaml.comments.CommentedMap(
            [("class", "Directory"), ("path", "a/directory/path")]
        ),
    }  # type: CWLObjectType
    if isinstance(inptype, MutableSequence):
        optional = False
        if "null" in inptype:
            inptype.remove("null")
            optional = True
        if len(inptype) == 1:
            example, comment = generate_example_input(inptype[0], default)
            if optional:
                if comment:
                    comment = "{} (optional)".format(comment)
                else:
                    comment = "optional"
        else:
            example = CommentedSeq()
            for index, entry in enumerate(inptype):
                value, e_comment = generate_example_input(entry, default)
                example.append(value)
                example.yaml_add_eol_comment(e_comment, index)
            if optional:
                comment = "optional"
    elif isinstance(inptype, Mapping) and "type" in inptype:
        if inptype["type"] == "array":
            first_item = cast(MutableSequence[CWLObjectType], inptype["items"])[0]
            items_len = len(cast(Sized, inptype["items"]))
            if items_len == 1 and "type" in first_item and first_item["type"] == "enum":
                # array of just an enum then list all the options
                example = first_item["symbols"]
                if "name" in first_item:
                    comment = u'array of type "{}".'.format(first_item["name"])
            else:
                value, comment = generate_example_input(inptype["items"], None)
                comment = "array of " + comment
                if items_len == 1:
                    example = [value]
                else:
                    example = value
            if default is not None:
                example = default
        elif inptype["type"] == "enum":
            symbols = cast(List[str], inptype["symbols"])
            if default is not None:
                example = default
            elif "default" in inptype:
                example = inptype["default"]
            elif len(cast(Sized, inptype["symbols"])) == 1:
                example = symbols[0]
            else:
                example = "{}_enum_value".format(inptype.get("name", "valid"))
            comment = u'enum; valid values: "{}"'.format('", "'.join(symbols))
        elif inptype["type"] == "record":
            example = yaml.comments.CommentedMap()
            if "name" in inptype:
                comment = u'"{}" record type.'.format(inptype["name"])
            for field in cast(List[CWLObjectType], inptype["fields"]):
                value, f_comment = generate_example_input(field["type"], None)
                example.insert(0, shortname(cast(str, field["name"])), value, f_comment)
        elif "default" in inptype:
            example = inptype["default"]
            comment = u'default value of type "{}".'.format(inptype["type"])
        else:
            example = defaults.get(cast(str, inptype["type"]), str(inptype))
            comment = u'type "{}".'.format(inptype["type"])
    else:
        if not default:
            example = defaults.get(str(inptype), str(inptype))
            comment = u'type "{}"'.format(inptype)
        else:
            example = default
            comment = u'default value of type "{}".'.format(inptype)
    return example, comment


def realize_input_schema(
    input_types: MutableSequence[CWLObjectType],
    schema_defs: MutableMapping[str, CWLObjectType],
) -> MutableSequence[CWLObjectType]:
    """Replace references to named typed with the actual types."""
    for index, entry in enumerate(input_types):
        if isinstance(entry, str):
            if "#" in entry:
                _, input_type_name = entry.split("#")
            else:
                input_type_name = entry
            if input_type_name in schema_defs:
                entry = input_types[index] = schema_defs[input_type_name]
        if isinstance(entry, Mapping):
            if isinstance(entry["type"], str) and "#" in entry["type"]:
                _, input_type_name = entry["type"].split("#")
                if input_type_name in schema_defs:
                    input_types[index]["type"] = cast(
                        CWLOutputAtomType,
                        realize_input_schema(
                            cast(
                                MutableSequence[CWLObjectType],
                                schema_defs[input_type_name],
                            ),
                            schema_defs,
                        ),
                    )
            if isinstance(entry["type"], MutableSequence):
                input_types[index]["type"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[CWLObjectType], entry["type"]), schema_defs
                    ),
                )
            if isinstance(entry["type"], Mapping):
                input_types[index]["type"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        [cast(CWLObjectType, input_types[index]["type"])], schema_defs
                    ),
                )
            if entry["type"] == "array":
                items = (
                    entry["items"]
                    if not isinstance(entry["items"], str)
                    else [entry["items"]]
                )
                input_types[index]["items"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[CWLObjectType], items), schema_defs
                    ),
                )
            if entry["type"] == "record":
                input_types[index]["fields"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[CWLObjectType], entry["fields"]),
                        schema_defs,
                    ),
                )
    return input_types


def generate_input_template(tool: Process) -> CWLObjectType:
    """Generate an example input object for the given CWL process."""
    template = yaml.comments.CommentedMap()
    for inp in realize_input_schema(tool.tool["inputs"], tool.schemaDefs):
        name = shortname(cast(str, inp["id"]))
        value, comment = generate_example_input(inp["type"], inp.get("default", None))
        template.insert(0, name, value, comment)
    return template


def load_job_order(
    args: argparse.Namespace,
    stdin: IO[Any],
    fetcher_constructor: Optional[FetcherCallableType],
    overrides_list: List[CWLObjectType],
    tool_file_uri: str,
) -> Tuple[Optional[CWLObjectType], str, Loader]:

    job_order_object = None
    job_order_file = None

    _jobloaderctx = jobloaderctx.copy()
    loader = Loader(_jobloaderctx, fetcher_constructor=fetcher_constructor)

    if len(args.job_order) == 1 and args.job_order[0][0] != "-":
        job_order_file = args.job_order[0]
    elif len(args.job_order) == 1 and args.job_order[0] == "-":
        job_order_object = yaml.main.round_trip_load(stdin)
        job_order_object, _ = loader.resolve_all(
            job_order_object, file_uri(os.getcwd()) + "/"
        )
    else:
        job_order_file = None

    if job_order_object is not None:
        input_basedir = args.basedir if args.basedir else os.getcwd()
    elif job_order_file is not None:
        input_basedir = (
            args.basedir
            if args.basedir
            else os.path.abspath(os.path.dirname(job_order_file))
        )
        job_order_object, _ = loader.resolve_ref(job_order_file, checklinks=False)

    if (
        job_order_object is not None
        and "http://commonwl.org/cwltool#overrides" in job_order_object
    ):
        ov_uri = file_uri(job_order_file or input_basedir)
        overrides_list.extend(
            resolve_overrides(job_order_object, ov_uri, tool_file_uri)
        )
        del job_order_object["http://commonwl.org/cwltool#overrides"]

    if job_order_object is None:
        input_basedir = args.basedir if args.basedir else os.getcwd()

    if job_order_object is not None and not isinstance(
        job_order_object, MutableMapping
    ):
        _logger.error(
            "CWL input object at %s is not formatted correctly, it should be a "
            "JSON/YAML dictionay, not %s.\n"
            "Raw input object:\n%s",
            job_order_file or "stdin",
            type(job_order_object),
            job_order_object,
        )
        sys.exit(1)
    return (job_order_object, input_basedir, loader)


def init_job_order(
    job_order_object: Optional[CWLObjectType],
    args: argparse.Namespace,
    process: Process,
    loader: Loader,
    stdout: Union[TextIO, StreamWriter],
    print_input_deps: bool = False,
    relative_deps: str = "primary",
    make_fs_access: Callable[[str], StdFsAccess] = StdFsAccess,
    input_basedir: str = "",
    secret_store: Optional[SecretStore] = None,
    input_required: bool = True,
) -> CWLObjectType:
    secrets_req, _ = process.get_requirement("http://commonwl.org/cwltool#Secrets")
    if job_order_object is None:
        namemap = {}  # type: Dict[str, str]
        records = []  # type: List[str]
        toolparser = generate_parser(
            argparse.ArgumentParser(prog=args.workflow),
            process,
            namemap,
            records,
            input_required,
        )
        if args.tool_help:
            toolparser.print_help()
            exit(0)
        cmd_line = vars(toolparser.parse_args(args.job_order))
        for record_name in records:
            record = {}
            record_items = {
                k: v for k, v in cmd_line.items() if k.startswith(record_name)
            }
            for key, value in record_items.items():
                record[key[len(record_name) + 1 :]] = value
                del cmd_line[key]
            cmd_line[str(record_name)] = record
        if "job_order" in cmd_line and cmd_line["job_order"]:
            try:
                job_order_object = cast(
                    CWLObjectType,
                    loader.resolve_ref(cmd_line["job_order"])[0],
                )
            except Exception:
                _logger.exception(
                    "Failed to resolv job_order: %s", cmd_line["job_order"]
                )
                exit(1)
        else:
            job_order_object = {"id": args.workflow}

        del cmd_line["job_order"]

        job_order_object.update({namemap[k]: v for k, v in cmd_line.items()})

        if secret_store and secrets_req:
            secret_store.store(
                [shortname(sc) for sc in cast(List[str], secrets_req["secrets"])],
                job_order_object,
            )

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Parsed job order from command line: %s",
                json_dumps(job_order_object, indent=4),
            )

    for inp in process.tool["inputs"]:
        if "default" in inp and (
            not job_order_object or shortname(inp["id"]) not in job_order_object
        ):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

    if job_order_object is None:
        if process.tool["inputs"]:
            if toolparser is not None:
                print("\nOptions for {} ".format(args.workflow))
                toolparser.print_help()
            _logger.error("")
            _logger.error("Input object required, use --help for details")
            exit(1)
        else:
            job_order_object = {}

    if print_input_deps:
        basedir = None  # type: Optional[str]
        uri = cast(str, job_order_object["id"])
        if uri == args.workflow:
            basedir = os.path.dirname(uri)
            uri = ""
        printdeps(
            job_order_object,
            loader,
            stdout,
            relative_deps,
            uri,
            basedir=basedir,
            nestdirs=False,
        )
        exit(0)

    def path_to_loc(p: CWLObjectType) -> None:
        if "location" not in p and "path" in p:
            p["location"] = p["path"]
            del p["path"]

    ns = {}  # type: ContextType
    ns.update(cast(ContextType, job_order_object.get("$namespaces", {})))
    ns.update(cast(ContextType, process.metadata.get("$namespaces", {})))
    ld = Loader(ns)

    def expand_formats(p: CWLObjectType) -> None:
        if "format" in p:
            p["format"] = ld.expand_url(cast(str, p["format"]), "")

    visit_class(job_order_object, ("File", "Directory"), path_to_loc)
    visit_class(
        job_order_object,
        ("File",),
        functools.partial(add_sizes, make_fs_access(input_basedir)),
    )
    visit_class(job_order_object, ("File",), expand_formats)
    adjustDirObjs(job_order_object, trim_listing)
    normalizeFilesDirs(job_order_object)

    if secret_store and secrets_req:
        secret_store.store(
            [shortname(sc) for sc in cast(List[str], secrets_req["secrets"])],
            job_order_object,
        )

    if "cwl:tool" in job_order_object:
        del job_order_object["cwl:tool"]
    if "id" in job_order_object:
        del job_order_object["id"]
    return job_order_object


def make_relative(base: str, obj: CWLObjectType) -> None:
    """Relativize the location URI of a File or Directory object."""
    uri = cast(str, obj.get("location", obj.get("path")))
    if ":" in uri.split("/")[0] and not uri.startswith("file://"):
        pass
    else:
        if uri.startswith("file://"):
            uri = uri_file_path(uri)
            obj["location"] = os.path.relpath(uri, base)


def printdeps(
    obj: CWLObjectType,
    document_loader: Loader,
    stdout: Union[TextIO, StreamWriter],
    relative_deps: str,
    uri: str,
    basedir: Optional[str] = None,
    nestdirs: bool = True,
) -> None:
    """Print a JSON representation of the dependencies of the CWL document."""
    deps = find_deps(obj, document_loader, uri, basedir=basedir, nestdirs=nestdirs)
    if relative_deps == "primary":
        base = basedir if basedir else os.path.dirname(uri_file_path(str(uri)))
    elif relative_deps == "cwd":
        base = os.getcwd()
    visit_class(deps, ("File", "Directory"), functools.partial(make_relative, base))
    stdout.write(json_dumps(deps, indent=4))


def prov_deps(
    obj: CWLObjectType,
    document_loader: Loader,
    uri: str,
    basedir: Optional[str] = None,
) -> CWLObjectType:
    deps = find_deps(obj, document_loader, uri, basedir=basedir)

    def remove_non_cwl(deps: CWLObjectType) -> None:
        if "secondaryFiles" in deps:
            sec_files = cast(List[CWLObjectType], deps["secondaryFiles"])
            for index, entry in enumerate(sec_files):
                if not ("format" in entry and entry["format"] == CWL_IANA):
                    del sec_files[index]
                else:
                    remove_non_cwl(entry)

    remove_non_cwl(deps)
    return deps


def find_deps(
    obj: CWLObjectType,
    document_loader: Loader,
    uri: str,
    basedir: Optional[str] = None,
    nestdirs: bool = True,
) -> CWLObjectType:
    """Find the dependencies of the CWL document."""
    deps = {
        "class": "File",
        "location": uri,
        "format": CWL_IANA,
    }  # type: CWLObjectType

    def loadref(base: str, uri: str) -> Union[CommentedMap, CommentedSeq, str, None]:
        return document_loader.fetch(document_loader.fetcher.urljoin(base, uri))

    sfs = scandeps(
        basedir if basedir else uri,
        obj,
        {"$import", "run"},
        {"$include", "$schemas", "location"},
        loadref,
        nestdirs=nestdirs,
    )
    if sfs is not None:
        deps["secondaryFiles"] = cast(MutableSequence[CWLOutputAtomType], sfs)

    return deps


def print_pack(
    loadingContext: LoadingContext,
    uri: str,
) -> str:
    """Return a CWL serialization of the CWL document in JSON."""
    packed = pack(loadingContext, uri)
    if len(cast(Sized, packed["$graph"])) > 1:
        return json_dumps(packed, indent=4)
    return json_dumps(
        cast(MutableSequence[CWLObjectType], packed["$graph"])[0], indent=4
    )


def supported_cwl_versions(enable_dev: bool) -> List[str]:
    # ALLUPDATES and UPDATES are dicts
    if enable_dev:
        versions = list(ALLUPDATES)
    else:
        versions = list(UPDATES)
    versions.sort()
    return versions


def configure_logging(
    args: argparse.Namespace,
    stderr_handler: logging.Handler,
    runtimeContext: RuntimeContext,
) -> None:
    rdflib_logger = logging.getLogger("rdflib.term")
    rdflib_logger.addHandler(stderr_handler)
    rdflib_logger.setLevel(logging.ERROR)
    if args.quiet:
        # Silence STDERR, not an eventual provenance log file
        stderr_handler.setLevel(logging.WARN)
    if runtimeContext.debug:
        # Increase to debug for both stderr and provenance log file
        _logger.setLevel(logging.DEBUG)
        stderr_handler.setLevel(logging.DEBUG)
        rdflib_logger.setLevel(logging.DEBUG)
    fmtclass = coloredlogs.ColoredFormatter if args.enable_color else logging.Formatter
    formatter = fmtclass("%(levelname)s %(message)s")
    if args.timestamps:
        formatter = fmtclass(
            "[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"
        )
    stderr_handler.setFormatter(formatter)


def setup_schema(
    args: argparse.Namespace, custom_schema_callback: Optional[Callable[[], None]]
) -> None:
    if custom_schema_callback is not None:
        custom_schema_callback()
    elif args.enable_ext:
        with pkg_resources.resource_stream(__name__, "extensions.yml") as res:
            ext10 = res.read().decode("utf-8")
        with pkg_resources.resource_stream(__name__, "extensions-v1.1.yml") as res:
            ext11 = res.read().decode("utf-8")
        use_custom_schema("v1.0", "http://commonwl.org/cwltool", ext10)
        use_custom_schema("v1.1", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2.0-dev1", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2.0-dev2", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2.0-dev3", "http://commonwl.org/cwltool", ext11)
    else:
        use_standard_schema("v1.0")
        use_standard_schema("v1.1")
        use_standard_schema("v1.2.0-dev1")
        use_standard_schema("v1.2.0-dev2")
        use_standard_schema("v1.2.0-dev3")


class ProvLogFormatter(logging.Formatter):
    """Enforce ISO8601 with both T and Z."""

    def __init__(self) -> None:
        """Use the default formatter with our custom formatstring."""
        super(ProvLogFormatter, self).__init__("[%(asctime)sZ] %(message)s")

    def formatTime(
        self, record: logging.LogRecord, datefmt: Optional[str] = None
    ) -> str:
        formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        with_msecs = "%s,%03f" % (formatted_time, record.msecs)
        return with_msecs


def setup_provenance(
    args: argparse.Namespace,
    argsl: List[str],
    runtimeContext: RuntimeContext,
) -> Optional[int]:
    if not args.compute_checksum:
        _logger.error("--provenance incompatible with --no-compute-checksum")
        return 1
    ro = ResearchObject(
        getdefault(runtimeContext.make_fs_access, StdFsAccess)(""),
        temp_prefix_ro=args.tmpdir_prefix,
        orcid=args.orcid,
        full_name=args.cwl_full_name,
    )
    runtimeContext.research_obj = ro
    log_file_io = ro.open_log_file_for_activity(ro.engine_uuid)
    prov_log_handler = logging.StreamHandler(cast(IO[str], log_file_io))

    prov_log_handler.setFormatter(ProvLogFormatter())
    _logger.addHandler(prov_log_handler)
    _logger.debug("[provenance] Logging to %s", log_file_io)
    if argsl is not None:
        # Log cwltool command line options to provenance file
        _logger.info("[cwltool] %s %s", sys.argv[0], " ".join(argsl))
    _logger.debug("[cwltool] Arguments: %s", args)
    return None


def setup_loadingContext(
    loadingContext: Optional[LoadingContext],
    runtimeContext: RuntimeContext,
    args: argparse.Namespace,
) -> LoadingContext:
    if loadingContext is None:
        loadingContext = LoadingContext(vars(args))
    else:
        loadingContext = loadingContext.copy()
    loadingContext.loader = default_loader(
        loadingContext.fetcher_constructor,
        enable_dev=args.enable_dev,
        doc_cache=args.doc_cache,
    )
    loadingContext.research_obj = runtimeContext.research_obj
    loadingContext.disable_js_validation = args.disable_js_validation or (
        not args.do_validate
    )
    loadingContext.construct_tool_object = getdefault(
        loadingContext.construct_tool_object, workflow.default_make_tool
    )
    loadingContext.resolver = getdefault(loadingContext.resolver, tool_resolver)
    if loadingContext.do_update is None:
        loadingContext.do_update = not (args.pack or args.print_subgraph)

    return loadingContext


def make_template(
    tool: Process,
) -> None:
    """Make a template CWL input object for the give Process."""

    def my_represent_none(
        self: Any, data: Any
    ) -> Any:  # pylint: disable=unused-argument
        """Force clean representation of 'null'."""
        return self.represent_scalar("tag:yaml.org,2002:null", "null")

    yaml.representer.RoundTripRepresenter.add_representer(type(None), my_represent_none)
    yaml.main.round_trip_dump(
        generate_input_template(tool),
        sys.stdout,
        default_flow_style=False,
        indent=4,
        block_seq_indent=2,
    )


def choose_target(
    args: argparse.Namespace,
    tool: Process,
    loadingContext: LoadingContext,
) -> Optional[Process]:
    """Walk the given Workflow and find the process that matches args.target."""
    if loadingContext.loader is None:
        raise Exception("loadingContext.loader cannot be None")

    if isinstance(tool, Workflow):
        url = urllib.parse.urlparse(tool.tool["id"])
        if url.fragment:
            extracted = get_subgraph(
                [tool.tool["id"] + "/" + r for r in args.target], tool
            )
        else:
            extracted = get_subgraph(
                [
                    loadingContext.loader.fetcher.urljoin(tool.tool["id"], "#" + r)
                    for r in args.target
                ],
                tool,
            )
    else:
        _logger.error("Can only use --target on Workflows")
        return None
    if isinstance(loadingContext.loader.idx, MutableMapping):
        loadingContext.loader.idx[extracted["id"]] = extracted
        tool = make_tool(extracted["id"], loadingContext)
    else:
        raise Exception("Missing loadingContext.loader.idx!")

    return tool


def check_working_directories(
    runtimeContext: RuntimeContext,
) -> Optional[int]:
    """Make any needed working directories."""
    for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
        if (
            getattr(runtimeContext, dirprefix)
            and getattr(runtimeContext, dirprefix) != DEFAULT_TMP_PREFIX
        ):
            sl = (
                "/"
                if getattr(runtimeContext, dirprefix).endswith("/")
                or dirprefix == "cachedir"
                else ""
            )
            setattr(
                runtimeContext,
                dirprefix,
                os.path.abspath(getattr(runtimeContext, dirprefix)) + sl,
            )
            if not os.path.exists(os.path.dirname(getattr(runtimeContext, dirprefix))):
                try:
                    os.makedirs(os.path.dirname(getattr(runtimeContext, dirprefix)))
                except Exception:
                    _logger.exception("Failed to create directory.")
                    return 1
    return None


def main(
    argsl: Optional[List[str]] = None,
    args: Optional[argparse.Namespace] = None,
    job_order_object: Optional[CWLObjectType] = None,
    stdin: IO[Any] = sys.stdin,
    stdout: Optional[Union[TextIO, StreamWriter]] = None,
    stderr: IO[Any] = sys.stderr,
    versionfunc: Callable[[], str] = versionstring,
    logger_handler: Optional[logging.Handler] = None,
    custom_schema_callback: Optional[Callable[[], None]] = None,
    executor: Optional[JobExecutor] = None,
    loadingContext: Optional[LoadingContext] = None,
    runtimeContext: Optional[RuntimeContext] = None,
    input_required: bool = True,
) -> int:
    if not stdout:  # force UTF-8 even if the console is configured differently
        if hasattr(sys.stdout, "encoding") and sys.stdout.encoding.upper() not in (
            "UTF-8",
            "UTF8",
        ):
            if hasattr(sys.stdout, "detach"):
                stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            else:
                stdout = getwriter("utf-8")(sys.stdout)  # type: ignore
        else:
            stdout = sys.stdout

    _logger.removeHandler(defaultStreamHandler)
    stderr_handler = logger_handler
    if stderr_handler is not None:
        _logger.addHandler(stderr_handler)
    else:
        coloredlogs.install(logger=_logger, stream=stderr)
        stderr_handler = _logger.handlers[-1]
    workflowobj = None
    prov_log_handler = None  # type: Optional[logging.StreamHandler]
    try:
        if args is None:
            if argsl is None:
                argsl = sys.argv[1:]
            addl = []  # type: List[str]
            if "CWLTOOL_OPTIONS" in os.environ:
                addl = os.environ["CWLTOOL_OPTIONS"].split(" ")
            parser = arg_parser()
            argcomplete.autocomplete(parser)
            args = parser.parse_args(addl + argsl)
            if args.record_container_id:
                if not args.cidfile_dir:
                    args.cidfile_dir = os.getcwd()
                del args.record_container_id

        if runtimeContext is None:
            runtimeContext = RuntimeContext(vars(args))
        else:
            runtimeContext = runtimeContext.copy()

        # If on Windows platform, a default Docker Container is used if not
        # explicitely provided by user
        if onWindows() and not runtimeContext.default_container:
            # This docker image is a minimal alpine image with bash installed
            # (size 6 mb). source: https://github.com/frol/docker-alpine-bash
            runtimeContext.default_container = windows_default_container_id

        # If caller parsed its own arguments, it may not include every
        # cwltool option, so fill in defaults to avoid crashing when
        # dereferencing them in args.
        for key, val in get_default_args().items():
            if not hasattr(args, key):
                setattr(args, key, val)

        configure_logging(args, stderr_handler, runtimeContext)

        if args.version:
            print(versionfunc())
            return 0
        _logger.info(versionfunc())

        if args.print_supported_versions:
            print("\n".join(supported_cwl_versions(args.enable_dev)))
            return 0

        if not args.workflow:
            if os.path.isfile("CWLFile"):
                args.workflow = "CWLFile"
            else:
                _logger.error("CWL document required, no input file was provided")
                parser.print_help()
                return 1
        if args.relax_path_checks:
            command_line_tool.ACCEPTLIST_RE = command_line_tool.ACCEPTLIST_EN_RELAXED_RE

        if args.ga4gh_tool_registries:
            ga4gh_tool_registries[:] = args.ga4gh_tool_registries
        if not args.enable_ga4gh_tool_registry:
            del ga4gh_tool_registries[:]

        if args.mpi_config_file is not None:
            runtimeContext.mpi_config = MpiConfig.load(args.mpi_config_file)

        setup_schema(args, custom_schema_callback)

        if args.provenance:
            if argsl is None:
                raise Exception("argsl cannot be None")
            if setup_provenance(args, argsl, runtimeContext) is not None:
                return 1

        loadingContext = setup_loadingContext(loadingContext, runtimeContext, args)

        uri, tool_file_uri = resolve_tool_uri(
            args.workflow,
            resolver=loadingContext.resolver,
            fetcher_constructor=loadingContext.fetcher_constructor,
        )

        try_again_msg = (
            "" if args.debug else ", try again with --debug for more information"
        )

        try:
            job_order_object, input_basedir, jobloader = load_job_order(
                args,
                stdin,
                loadingContext.fetcher_constructor,
                loadingContext.overrides_list,
                tool_file_uri,
            )

            if args.overrides:
                loadingContext.overrides_list.extend(
                    load_overrides(
                        file_uri(os.path.abspath(args.overrides)), tool_file_uri
                    )
                )

            loadingContext, workflowobj, uri = fetch_document(uri, loadingContext)

            if args.print_deps and loadingContext.loader:
                printdeps(
                    workflowobj, loadingContext.loader, stdout, args.relative_deps, uri
                )
                return 0

            loadingContext, uri = resolve_and_validate_document(
                loadingContext,
                workflowobj,
                uri,
                preprocess_only=(args.print_pre or args.pack),
                skip_schemas=args.skip_schemas,
            )

            if loadingContext.loader is None:
                raise Exception("Impossible code path.")
            processobj, metadata = loadingContext.loader.resolve_ref(uri)
            processobj = cast(CommentedMap, processobj)
            if args.pack:
                stdout.write(print_pack(loadingContext, uri))
                return 0

            if args.provenance and runtimeContext.research_obj:
                # Can't really be combined with args.pack at same time
                runtimeContext.research_obj.packed_workflow(
                    print_pack(loadingContext, uri)
                )

            if args.print_pre:
                stdout.write(
                    json_dumps(
                        processobj, indent=4, sort_keys=True, separators=(",", ": ")
                    )
                )
                return 0

            tool = make_tool(uri, loadingContext)
            if args.make_template:
                make_template(tool)
                return 0

            if args.validate:
                print("{} is valid CWL.".format(args.workflow))
                return 0

            if args.print_rdf:
                stdout.write(
                    printrdf(tool, loadingContext.loader.ctx, args.rdf_serializer)
                )
                return 0

            if args.print_dot:
                printdot(tool, loadingContext.loader.ctx, stdout)
                return 0

            if args.print_targets:
                for f in ("outputs", "steps", "inputs"):
                    if tool.tool[f]:
                        _logger.info("%s%s targets:", f[0].upper(), f[1:-1])
                        stdout.write(
                            "  "
                            + "\n  ".join([shortname(t["id"]) for t in tool.tool[f]])
                            + "\n"
                        )
                return 0

            if args.target:
                ctool = choose_target(args, tool, loadingContext)
                if ctool is None:
                    return 1
                else:
                    tool = ctool

            if args.print_subgraph:
                if "name" in tool.tool:
                    del tool.tool["name"]
                stdout.write(
                    json_dumps(
                        tool.tool, indent=4, sort_keys=True, separators=(",", ": ")
                    )
                )
                return 0

        except (ValidationException) as exc:
            _logger.error(
                "Tool definition failed validation:\n%s", str(exc), exc_info=args.debug
            )
            return 1
        except (RuntimeError, WorkflowException) as exc:
            _logger.error(
                "Tool definition failed initialization:\n%s",
                str(exc),
                exc_info=args.debug,
            )
            return 1
        except Exception as exc:
            _logger.error(
                "I'm sorry, I couldn't load this CWL file%s.\nThe error was: %s",
                try_again_msg,
                str(exc) if not args.debug else "",
                exc_info=args.debug,
            )
            return 1

        if isinstance(tool, int):
            return tool

        # If on MacOS platform, TMPDIR must be set to be under one of the
        # shared volumes in Docker for Mac
        # More info: https://dockstore.org/docs/faq
        if sys.platform == "darwin":
            default_mac_path = "/private/tmp/docker_tmp"
            if runtimeContext.tmp_outdir_prefix == DEFAULT_TMP_PREFIX:
                runtimeContext.tmp_outdir_prefix = default_mac_path
            if runtimeContext.tmpdir_prefix == DEFAULT_TMP_PREFIX:
                runtimeContext.tmpdir_prefix = default_mac_path

        if check_working_directories(runtimeContext) is not None:
            return 1

        if args.cachedir:
            if args.move_outputs == "move":
                runtimeContext.move_outputs = "copy"
            runtimeContext.tmp_outdir_prefix = args.cachedir

        runtimeContext.secret_store = getdefault(
            runtimeContext.secret_store, SecretStore()
        )
        runtimeContext.make_fs_access = getdefault(
            runtimeContext.make_fs_access, StdFsAccess
        )

        if not executor:
            if args.parallel:
                temp_executor = MultithreadedJobExecutor()
                runtimeContext.select_resources = temp_executor.select_resources
                real_executor = temp_executor  # type: JobExecutor
            else:
                real_executor = SingleJobExecutor()
        else:
            real_executor = executor

        try:
            runtimeContext.basedir = input_basedir

            if isinstance(tool, ProcessGenerator):
                tfjob_order = {}  # type: CWLObjectType
                if loadingContext.jobdefaults:
                    tfjob_order.update(loadingContext.jobdefaults)
                if job_order_object:
                    tfjob_order.update(job_order_object)
                tfout, tfstatus = real_executor(
                    tool.embedded_tool, tfjob_order, runtimeContext
                )
                if not tfout or tfstatus != "success":
                    raise WorkflowException(
                        "ProcessGenerator failed to generate workflow"
                    )
                tool, job_order_object = tool.result(tfjob_order, tfout, runtimeContext)
                if not job_order_object:
                    job_order_object = None

            try:
                initialized_job_order_object = init_job_order(
                    job_order_object,
                    args,
                    tool,
                    jobloader,
                    stdout,
                    print_input_deps=args.print_input_deps,
                    relative_deps=args.relative_deps,
                    make_fs_access=runtimeContext.make_fs_access,
                    input_basedir=input_basedir,
                    secret_store=runtimeContext.secret_store,
                    input_required=input_required,
                )
            except SystemExit as err:
                return err.code

            del args.workflow
            del args.job_order

            conf_file = getattr(
                args, "beta_dependency_resolvers_configuration", None
            )  # str
            use_conda_dependencies = getattr(
                args, "beta_conda_dependencies", None
            )  # str

            if conf_file or use_conda_dependencies:
                runtimeContext.job_script_provider = DependenciesConfiguration(args)
            else:
                runtimeContext.find_default_container = functools.partial(
                    find_default_container,
                    default_container=runtimeContext.default_container,
                    use_biocontainers=args.beta_use_biocontainers,
                )

            (out, status) = real_executor(
                tool, initialized_job_order_object, runtimeContext, logger=_logger
            )

            if out is not None:
                if runtimeContext.research_obj is not None:
                    runtimeContext.research_obj.create_job(out, True)

                    def remove_at_id(doc: CWLObjectType) -> None:
                        for key in list(doc.keys()):
                            if key == "@id":
                                del doc[key]
                            else:
                                value = doc[key]
                                if isinstance(value, MutableMapping):
                                    remove_at_id(value)
                                elif isinstance(value, MutableSequence):
                                    for entry in value:
                                        if isinstance(entry, MutableMapping):
                                            remove_at_id(entry)

                    remove_at_id(out)
                    visit_class(
                        out,
                        ("File",),
                        functools.partial(add_sizes, runtimeContext.make_fs_access("")),
                    )

                def loc_to_path(obj: CWLObjectType) -> None:
                    for field in ("path", "nameext", "nameroot", "dirname"):
                        if field in obj:
                            del obj[field]
                    if cast(str, obj["location"]).startswith("file://"):
                        obj["path"] = uri_file_path(cast(str, obj["location"]))

                visit_class(out, ("File", "Directory"), loc_to_path)

                # Unsetting the Generation from final output object
                visit_class(out, ("File",), MutationManager().unset_generation)

                if isinstance(out, str):
                    stdout.write(out)
                else:
                    stdout.write(json_dumps(out, indent=4, ensure_ascii=False))
                stdout.write("\n")
                if hasattr(stdout, "flush"):
                    stdout.flush()

            if status != "success":
                _logger.warning("Final process status is %s", status)
                return 1
            _logger.info("Final process status is %s", status)
            return 0

        except (ValidationException) as exc:
            _logger.error(
                "Input object failed validation:\n%s", str(exc), exc_info=args.debug
            )
            return 1
        except UnsupportedRequirement as exc:
            _logger.error(
                "Workflow or tool uses unsupported feature:\n%s",
                str(exc),
                exc_info=args.debug,
            )
            return 33
        except WorkflowException as exc:
            _logger.error(
                "Workflow error%s:\n%s",
                try_again_msg,
                strip_dup_lineno(str(exc)),
                exc_info=args.debug,
            )
            return 1
        except Exception as exc:  # pylint: disable=broad-except
            _logger.error(
                "Unhandled error%s:\n  %s",
                try_again_msg,
                str(exc),
                exc_info=args.debug,
            )
            return 1

    finally:
        if (
            args
            and runtimeContext
            and runtimeContext.research_obj
            and workflowobj
            and loadingContext
        ):
            research_obj = runtimeContext.research_obj
            if loadingContext.loader is not None:
                research_obj.generate_snapshot(
                    prov_deps(workflowobj, loadingContext.loader, uri)
                )
            else:
                _logger.warning(
                    "Unable to generate provenance snapshot "
                    " due to missing loadingContext.loader."
                )
            if prov_log_handler is not None:
                # Stop logging so we won't half-log adding ourself to RO
                _logger.debug(
                    "[provenance] Closing provenance log file %s", prov_log_handler
                )
                _logger.removeHandler(prov_log_handler)
                # Ensure last log lines are written out
                prov_log_handler.flush()
                # Underlying WritableBagFile will add the tagfile to the manifest
                prov_log_handler.stream.close()
                prov_log_handler.close()
            research_obj.close(args.provenance)

        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


def find_default_container(
    builder: HasReqsHints,
    default_container: Optional[str] = None,
    use_biocontainers: Optional[bool] = None,
) -> Optional[str]:
    """Find a container."""
    if not default_container and use_biocontainers:
        default_container = get_container_from_software_requirements(
            use_biocontainers, builder
        )
    return default_container


def run(*args, **kwargs):
    # type: (*Any, **Any) -> None
    """Run cwltool."""
    signal.signal(signal.SIGTERM, _signal_handler)
    try:
        sys.exit(main(*args, **kwargs))
    finally:
        _terminate_processes()


if __name__ == "__main__":
    run(sys.argv[1:])
