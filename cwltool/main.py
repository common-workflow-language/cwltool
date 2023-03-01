#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""Entry point for cwltool."""

import argparse
import copy
import functools
import io
import logging
import os
import signal
import subprocess  # nosec
import sys
import time
import urllib
import warnings
from codecs import getwriter
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
    Tuple,
    Union,
    cast,
)

import argcomplete
import coloredlogs
import pkg_resources  # part of setuptools
import ruamel.yaml
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.main import YAML
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import Loader, file_uri, uri_file_path
from schema_salad.sourceline import cmap, strip_dup_lineno
from schema_salad.utils import (
    ContextType,
    FetcherCallableType,
    json_dump,
    json_dumps,
    yaml_no_ts,
)

from . import CWL_CONTENT_TYPES, workflow
from .argparser import arg_parser, generate_parser, get_default_args
from .context import LoadingContext, RuntimeContext, getdefault
from .cwlrdf import printdot, printrdf
from .errors import (
    ArgumentException,
    GraphTargetMissingException,
    UnsupportedRequirement,
    WorkflowException,
)
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
from .loghandler import _logger, configure_logging, defaultStreamHandler
from .mpi import MpiConfig
from .mutation import MutationManager
from .pack import pack
from .process import (
    CWL_IANA,
    Process,
    add_sizes,
    mergedirs,
    scandeps,
    shortname,
    use_custom_schema,
    use_standard_schema,
)
from .procgenerator import ProcessGenerator
from .provenance import ResearchObject, WritableBagFile
from .resolver import ga4gh_tool_registries, tool_resolver
from .secrets import SecretStore
from .software_requirements import (
    DependenciesConfiguration,
    get_container_from_software_requirements,
)
from .stdfsaccess import StdFsAccess
from .subgraph import get_process, get_step, get_subgraph
from .update import ALLUPDATES, UPDATES
from .utils import (
    DEFAULT_TMP_PREFIX,
    CWLObjectType,
    CWLOutputAtomType,
    CWLOutputType,
    HasReqsHints,
    adjustDirObjs,
    normalizeFilesDirs,
    processes_to_kill,
    trim_listing,
    versionstring,
    visit_class,
)
from .workflow import Workflow

docker_exe: str


def _terminate_processes() -> None:
    """Kill all spawned processes.

    Processes to be killed must be appended to `utils.processes_to_kill`
    as they are spawned.

    An important caveat: since there's no supported way to kill another
    thread in Python, this function cannot stop other threads from
    continuing to execute while it kills the processes that they've
    spawned. This may occasionally lead to unexpected behaviour.
    """
    global docker_exe
    # It's possible that another thread will spawn a new task while
    # we're executing, so it's not safe to use a for loop here.
    while processes_to_kill:
        process = processes_to_kill.popleft()
        if isinstance(process.args, MutableSequence):
            args = process.args
        else:
            args = [process.args]
        cidfile = [str(arg).split("=")[1] for arg in args if "--cidfile" in str(arg)]
        if cidfile:  # Try to be nice
            try:
                with open(cidfile[0]) as inp_stream:
                    p = subprocess.Popen(  # nosec
                        [docker_exe, "kill", inp_stream.read()], shell=False  # nosec
                    )
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        p.kill()
            except FileNotFoundError:
                pass
        if process.stdin:
            process.stdin.close()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            pass
        process.kill()  # Always kill, even if we tried with the cidfile


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
        "File": ruamel.yaml.comments.CommentedMap([("class", "File"), ("path", "a/file/path")]),
        "Directory": ruamel.yaml.comments.CommentedMap(
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
                    comment = f"{comment} (optional)"
                else:
                    comment = "optional"
        else:
            example, comment = generate_example_input(inptype[0], default)
            type_names = []
            for entry in inptype:
                value, e_comment = generate_example_input(entry, default)
                if e_comment:
                    type_names.append(e_comment)
            comment = "one of " + ", ".join(type_names)
            if optional:
                comment = f"{comment} (optional)"
    elif isinstance(inptype, Mapping) and "type" in inptype:
        if inptype["type"] == "array":
            first_item = cast(MutableSequence[CWLObjectType], inptype["items"])[0]
            items_len = len(cast(Sized, inptype["items"]))
            if items_len == 1 and "type" in first_item and first_item["type"] == "enum":
                # array of just an enum then list all the options
                example = first_item["symbols"]
                if "name" in first_item:
                    comment = 'array of type "{}".'.format(first_item["name"])
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
            comment = 'enum; valid values: "{}"'.format('", "'.join(symbols))
        elif inptype["type"] == "record":
            example = ruamel.yaml.comments.CommentedMap()
            if "name" in inptype:
                comment = '"{}" record type.'.format(inptype["name"])
            else:
                comment = "Anonymous record type."
            for field in cast(List[CWLObjectType], inptype["fields"]):
                value, f_comment = generate_example_input(field["type"], None)
                example.insert(0, shortname(cast(str, field["name"])), value, f_comment)
        elif "default" in inptype:
            example = inptype["default"]
            comment = f"default value of type {inptype['type']!r}"
        else:
            example = defaults.get(cast(str, inptype["type"]), str(inptype))
            comment = f"type {inptype['type']!r}"
    else:
        if not default:
            example = defaults.get(str(inptype), str(inptype))
            comment = f"type {inptype!r}"
        else:
            example = default
            comment = f"default value of type {inptype!r}."
    return example, comment


def realize_input_schema(
    input_types: MutableSequence[Union[str, CWLObjectType]],
    schema_defs: MutableMapping[str, CWLObjectType],
) -> MutableSequence[Union[str, CWLObjectType]]:
    """Replace references to named typed with the actual types."""
    for index, entry in enumerate(input_types):
        if isinstance(entry, str):
            if "#" in entry:
                _, input_type_name = entry.split("#")
            else:
                input_type_name = entry
            if input_type_name in schema_defs:
                entry = input_types[index] = schema_defs[input_type_name]
        if isinstance(entry, MutableMapping):
            if isinstance(entry["type"], str) and "#" in entry["type"]:
                _, input_type_name = entry["type"].split("#")
                if input_type_name in schema_defs:
                    entry["type"] = cast(
                        CWLOutputAtomType,
                        realize_input_schema(
                            cast(
                                MutableSequence[Union[str, CWLObjectType]],
                                schema_defs[input_type_name],
                            ),
                            schema_defs,
                        ),
                    )
            if isinstance(entry["type"], MutableSequence):
                entry["type"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[Union[str, CWLObjectType]], entry["type"]),
                        schema_defs,
                    ),
                )
            if isinstance(entry["type"], Mapping):
                entry["type"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema([cast(CWLObjectType, entry["type"])], schema_defs),
                )
            if entry["type"] == "array":
                items = entry["items"] if not isinstance(entry["items"], str) else [entry["items"]]
                entry["items"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[Union[str, CWLObjectType]], items),
                        schema_defs,
                    ),
                )
            if entry["type"] == "record":
                entry["fields"] = cast(
                    CWLOutputAtomType,
                    realize_input_schema(
                        cast(MutableSequence[Union[str, CWLObjectType]], entry["fields"]),
                        schema_defs,
                    ),
                )
    return input_types


def generate_input_template(tool: Process) -> CWLObjectType:
    """Generate an example input object for the given CWL process."""
    template = ruamel.yaml.comments.CommentedMap()
    for inp in cast(
        List[MutableMapping[str, str]],
        realize_input_schema(tool.tool["inputs"], tool.schemaDefs),
    ):
        name = shortname(inp["id"])
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
        yaml = yaml_no_ts()
        job_order_object = yaml.load(stdin)
        job_order_object, _ = loader.resolve_all(job_order_object, file_uri(os.getcwd()) + "/")
    else:
        job_order_file = None

    if job_order_object is not None:
        input_basedir = args.basedir if args.basedir else os.getcwd()
    elif job_order_file is not None:
        input_basedir = (
            args.basedir if args.basedir else os.path.abspath(os.path.dirname(job_order_file))
        )
        job_order_object, _ = loader.resolve_ref(
            job_order_file,
            checklinks=False,
            content_types=CWL_CONTENT_TYPES,
        )

    if job_order_object is not None and "http://commonwl.org/cwltool#overrides" in job_order_object:
        ov_uri = file_uri(job_order_file or input_basedir)
        overrides_list.extend(resolve_overrides(job_order_object, ov_uri, tool_file_uri))
        del job_order_object["http://commonwl.org/cwltool#overrides"]

    if job_order_object is None:
        input_basedir = args.basedir if args.basedir else os.getcwd()

    if job_order_object is not None and not isinstance(job_order_object, MutableMapping):
        _logger.error(
            "CWL input object at %s is not formatted correctly, it should be a "
            "JSON/YAML dictionary, not %s.\n"
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
    stdout: IO[str],
    print_input_deps: bool = False,
    relative_deps: str = "primary",
    make_fs_access: Callable[[str], StdFsAccess] = StdFsAccess,
    input_basedir: str = "",
    secret_store: Optional[SecretStore] = None,
    input_required: bool = True,
    runtime_context: Optional[RuntimeContext] = None,
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
            loader.fetcher.urljoin,
            file_uri(os.getcwd()) + "/",
        )
        if args.tool_help:
            toolparser.print_help(stdout)
            exit(0)
        cmd_line = vars(toolparser.parse_args(args.job_order))
        for record_name in records:
            record = {}
            record_items = {k: v for k, v in cmd_line.items() if k.startswith(record_name)}
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
                _logger.exception("Failed to resolv job_order: %s", cmd_line["job_order"])
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
                json_dumps(job_order_object, indent=4, default=str),
            )

    for inp in process.tool["inputs"]:
        if "default" in inp and (
            not job_order_object or shortname(inp["id"]) not in job_order_object
        ):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

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

    if print_input_deps:
        if not runtime_context:
            raise RuntimeError("runtime_context is required for print_input_deps.")
        runtime_context.toplevel = True
        builder = process._init_job(job_order_object, runtime_context)
        builder.loadListing = "no_listing"
        builder.bind_input(
            process.inputs_record_schema, job_order_object, discover_secondaryFiles=True
        )
        basedir: Optional[str] = None
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
    stdout: IO[str],
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
    json_dump(deps, stdout, indent=4, default=str)


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
        deps["secondaryFiles"] = cast(MutableSequence[CWLOutputAtomType], mergedirs(sfs))

    return deps


def print_pack(
    loadingContext: LoadingContext,
    uri: str,
) -> str:
    """Return a CWL serialization of the CWL document in JSON."""
    packed = pack(loadingContext, uri)
    if len(cast(Sized, packed["$graph"])) > 1:
        target = packed
    else:
        target = cast(MutableSequence[CWLObjectType], packed["$graph"])[0]
    return json_dumps(target, indent=4, default=str)


def supported_cwl_versions(enable_dev: bool) -> List[str]:
    # ALLUPDATES and UPDATES are dicts
    if enable_dev:
        versions = list(ALLUPDATES)
    else:
        versions = list(UPDATES)
    versions.sort()
    return versions


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
        with pkg_resources.resource_stream(__name__, "extensions-v1.2.yml") as res:
            ext12 = res.read().decode("utf-8")
        use_custom_schema("v1.0", "http://commonwl.org/cwltool", ext10)
        use_custom_schema("v1.1", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2", "http://commonwl.org/cwltool", ext12)
        use_custom_schema("v1.2.0-dev1", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2.0-dev2", "http://commonwl.org/cwltool", ext11)
        use_custom_schema("v1.2.0-dev3", "http://commonwl.org/cwltool", ext11)
    else:
        use_standard_schema("v1.0")
        use_standard_schema("v1.1")
        use_standard_schema("v1.2")
        use_standard_schema("v1.2.0-dev1")
        use_standard_schema("v1.2.0-dev2")
        use_standard_schema("v1.2.0-dev3")


class ProvLogFormatter(logging.Formatter):
    """Enforce ISO8601 with both T and Z."""

    def __init__(self) -> None:
        """Use the default formatter with our custom formatstring."""
        super().__init__("[%(asctime)sZ] %(message)s")

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Override the default formatTime to include the timezone."""
        formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(float(record.created)))
        with_msecs = f"{formatted_time},{record.msecs:03f}"
        return with_msecs


ProvOut = Union[io.TextIOWrapper, WritableBagFile]


def setup_provenance(
    args: argparse.Namespace,
    argsl: List[str],
    runtimeContext: RuntimeContext,
) -> Tuple[ProvOut, "logging.StreamHandler[ProvOut]"]:
    if not args.compute_checksum:
        _logger.error("--provenance incompatible with --no-compute-checksum")
        raise ArgumentException()
    ro = ResearchObject(
        getdefault(runtimeContext.make_fs_access, StdFsAccess)(""),
        temp_prefix_ro=args.tmpdir_prefix,
        orcid=args.orcid,
        full_name=args.cwl_full_name,
    )
    runtimeContext.research_obj = ro
    log_file_io = ro.open_log_file_for_activity(ro.engine_uuid)
    prov_log_handler = logging.StreamHandler(log_file_io)

    prov_log_handler.setFormatter(ProvLogFormatter())
    _logger.addHandler(prov_log_handler)
    _logger.debug("[provenance] Logging to %s", log_file_io)
    if argsl is not None:
        # Log cwltool command line options to provenance file
        _logger.info("[cwltool] %s %s", sys.argv[0], " ".join(argsl))
    _logger.debug("[cwltool] Arguments: %s", args)
    return log_file_io, prov_log_handler


def setup_loadingContext(
    loadingContext: Optional[LoadingContext],
    runtimeContext: RuntimeContext,
    args: argparse.Namespace,
) -> LoadingContext:
    """Prepare a LoadingContext from the given arguments."""
    if loadingContext is None:
        loadingContext = LoadingContext(vars(args))
        loadingContext.singularity = runtimeContext.singularity
        loadingContext.podman = runtimeContext.podman
    else:
        loadingContext = loadingContext.copy()
    loadingContext.loader = default_loader(
        loadingContext.fetcher_constructor,
        enable_dev=args.enable_dev,
        doc_cache=args.doc_cache,
    )
    loadingContext.research_obj = runtimeContext.research_obj
    loadingContext.disable_js_validation = args.disable_js_validation or (not args.do_validate)
    loadingContext.construct_tool_object = getdefault(
        loadingContext.construct_tool_object, workflow.default_make_tool
    )
    loadingContext.resolver = getdefault(loadingContext.resolver, tool_resolver)
    if loadingContext.do_update is None:
        loadingContext.do_update = not (args.pack or args.print_subgraph)

    return loadingContext


def make_template(tool: Process, target: IO[str]) -> None:
    """Make a template CWL input object for the give Process."""

    def my_represent_none(self: Any, data: Any) -> Any:  # pylint: disable=unused-argument
        """Force clean representation of 'null'."""
        return self.represent_scalar("tag:yaml.org,2002:null", "null")

    ruamel.yaml.representer.RoundTripRepresenter.add_representer(type(None), my_represent_none)
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent = 4
    yaml.block_seq_indent = 2
    yaml.dump(
        generate_input_template(tool),
        target,
    )


def inherit_reqshints(tool: Process, parent: Process) -> None:
    """Copy down requirements and hints from ancestors of a given process."""
    for parent_req in parent.requirements:
        found = False
        for tool_req in tool.requirements:
            if parent_req["class"] == tool_req["class"]:
                found = True
                break
        if not found:
            tool.requirements.append(parent_req)
    for parent_hint in parent.hints:
        found = False
        for tool_req in tool.requirements:
            if parent_hint["class"] == tool_req["class"]:
                found = True
                break
        if not found:
            for tool_hint in tool.hints:
                if parent_hint["class"] == tool_hint["class"]:
                    found = True
                    break
            if not found:
                tool.hints.append(parent_hint)


def choose_target(
    args: argparse.Namespace,
    tool: Process,
    loading_context: LoadingContext,
) -> Optional[Process]:
    """Walk the Workflow, extract the subset matches all the args.targets."""
    if loading_context.loader is None:
        raise Exception("loading_context.loader cannot be None")

    if isinstance(tool, Workflow):
        url = urllib.parse.urlparse(tool.tool["id"])
        if url.fragment:
            extracted = get_subgraph(
                [tool.tool["id"] + "/" + r for r in args.target], tool, loading_context
            )
        else:
            extracted = get_subgraph(
                [
                    loading_context.loader.fetcher.urljoin(tool.tool["id"], "#" + r)
                    for r in args.target
                ],
                tool,
                loading_context,
            )
    else:
        _logger.error("Can only use --target on Workflows")
        return None
    if isinstance(loading_context.loader.idx, MutableMapping):
        loading_context.loader.idx[extracted["id"]] = extracted
        tool = make_tool(extracted["id"], loading_context)
    else:
        raise Exception("Missing loading_context.loader.idx!")

    return tool


def choose_step(
    args: argparse.Namespace,
    tool: Process,
    loading_context: LoadingContext,
) -> Optional[Process]:
    """Walk the given Workflow and extract just args.single_step."""
    if loading_context.loader is None:
        raise Exception("loading_context.loader cannot be None")

    if isinstance(tool, Workflow):
        url = urllib.parse.urlparse(tool.tool["id"])
        if url.fragment:
            step_id = tool.tool["id"] + "/" + args.single_step
        else:
            step_id = loading_context.loader.fetcher.urljoin(
                tool.tool["id"], "#" + args.single_step
            )
        extracted = get_step(tool, step_id, loading_context)
    else:
        _logger.error("Can only use --single-step on Workflows")
        return None
    if isinstance(loading_context.loader.idx, MutableMapping):
        loading_context.loader.idx[extracted["id"]] = cast(
            Union[CommentedMap, CommentedSeq, str, None], cmap(extracted)
        )
        tool = make_tool(extracted["id"], loading_context)
    else:
        raise Exception("Missing loading_context.loader.idx!")

    return tool


def choose_process(
    args: argparse.Namespace,
    tool: Process,
    loadingContext: LoadingContext,
) -> Optional[Process]:
    """Walk the given Workflow and extract just args.single_process."""
    if loadingContext.loader is None:
        raise Exception("loadingContext.loader cannot be None")

    if isinstance(tool, Workflow):
        url = urllib.parse.urlparse(tool.tool["id"])
        if url.fragment:
            step_id = tool.tool["id"] + "/" + args.single_process
        else:
            step_id = loadingContext.loader.fetcher.urljoin(
                tool.tool["id"], "#" + args.single_process
            )
        extracted, workflow_step = get_process(
            tool,
            step_id,
            loadingContext,
        )
    else:
        _logger.error("Can only use --single-process on Workflows")
        return None
    if isinstance(loadingContext.loader.idx, MutableMapping):
        loadingContext.loader.idx[extracted["id"]] = extracted
        new_tool = make_tool(extracted["id"], loadingContext)
    else:
        raise Exception("Missing loadingContext.loader.idx!")
    inherit_reqshints(new_tool, workflow_step)
    return new_tool


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
                if getattr(runtimeContext, dirprefix).endswith("/") or dirprefix == "cachedir"
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


def print_targets(
    tool: Process,
    stdout: IO[str],
    loading_context: LoadingContext,
    prefix: str = "",
) -> None:
    """Recursively find targets for --subgraph and friends."""
    for f in ("outputs", "inputs"):
        if tool.tool[f]:
            _logger.info("%s %s%s targets:", prefix[:-1], f[0].upper(), f[1:-1])
            print(
                "  " + "\n  ".join([f"{prefix}{shortname(t['id'])}" for t in tool.tool[f]]),
                file=stdout,
            )
    if "steps" in tool.tool:
        loading_context = copy.copy(loading_context)
        loading_context.requirements = tool.requirements
        loading_context.hints = tool.hints
        _logger.info("%s steps targets:", prefix[:-1])
        for t in tool.tool["steps"]:
            print(f"  {prefix}{shortname(t['id'])}", file=stdout)
            run: Union[str, Process, Dict[str, Any]] = t["run"]
            if isinstance(run, str):
                process = make_tool(run, loading_context)
            elif isinstance(run, dict):
                process = make_tool(cast(CommentedMap, cmap(run)), loading_context)
            else:
                process = run
            print_targets(process, stdout, loading_context, f"{prefix}{shortname(t['id'])}/")


def main(
    argsl: Optional[List[str]] = None,
    args: Optional[argparse.Namespace] = None,
    job_order_object: Optional[CWLObjectType] = None,
    stdin: IO[Any] = sys.stdin,
    stdout: Optional[IO[str]] = None,
    stderr: IO[Any] = sys.stderr,
    versionfunc: Callable[[], str] = versionstring,
    logger_handler: Optional[logging.Handler] = None,
    custom_schema_callback: Optional[Callable[[], None]] = None,
    executor: Optional[JobExecutor] = None,
    loadingContext: Optional[LoadingContext] = None,
    runtimeContext: Optional[RuntimeContext] = None,
    input_required: bool = True,
) -> int:
    if stdout is None:  # force UTF-8 even if the console is configured differently
        if hasattr(sys.stdout, "encoding") and sys.stdout.encoding.upper() not in (
            "UTF-8",
            "UTF8",
        ):
            if hasattr(sys.stdout, "detach"):
                stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            else:
                stdout = getwriter("utf-8")(sys.stdout)  # type: ignore[assignment,arg-type]
        else:
            stdout = sys.stdout
        stdout = cast(IO[str], stdout)

    _logger.removeHandler(defaultStreamHandler)
    stderr_handler = logger_handler
    if stderr_handler is not None:
        _logger.addHandler(stderr_handler)
    else:
        coloredlogs.install(logger=_logger, stream=stderr)
        stderr_handler = _logger.handlers[-1]
    workflowobj = None
    prov_log_handler: Optional[logging.StreamHandler[ProvOut]] = None
    global docker_exe
    try:
        if args is None:
            if argsl is None:
                argsl = sys.argv[1:]
            addl = []  # type: List[str]
            if "CWLTOOL_OPTIONS" in os.environ:
                c_opts = os.environ["CWLTOOL_OPTIONS"].split(" ")
                addl = [x for x in c_opts if x != ""]
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

        if runtimeContext.podman:
            docker_exe = "podman"
        else:
            docker_exe = "docker"
        # If caller parsed its own arguments, it may not include every
        # cwltool option, so fill in defaults to avoid crashing when
        # dereferencing them in args.
        for key, val in get_default_args().items():
            if not hasattr(args, key):
                setattr(args, key, val)

        configure_logging(
            stderr_handler,
            args.quiet,
            runtimeContext.debug,
            args.enable_color,
            args.timestamps,
        )

        if args.version:
            print(versionfunc(), file=stdout)
            return 0
        _logger.info(versionfunc())

        if args.print_supported_versions:
            print("\n".join(supported_cwl_versions(args.enable_dev)), file=stdout)
            return 0

        if not args.workflow:
            if os.path.isfile("CWLFile"):
                args.workflow = "CWLFile"
            else:
                _logger.error("CWL document required, no input file was provided")
                parser.print_help(stderr)
                return 1

        if args.ga4gh_tool_registries:
            ga4gh_tool_registries[:] = args.ga4gh_tool_registries
        if not args.enable_ga4gh_tool_registry:
            del ga4gh_tool_registries[:]

        if args.mpi_config_file is not None:
            runtimeContext.mpi_config = MpiConfig.load(args.mpi_config_file)

        setup_schema(args, custom_schema_callback)

        prov_log_stream: Optional[Union[io.TextIOWrapper, WritableBagFile]] = None
        if args.provenance:
            if argsl is None:
                raise Exception("argsl cannot be None")
            try:
                prov_log_stream, prov_log_handler = setup_provenance(args, argsl, runtimeContext)
            except ArgumentException:
                return 1

        loadingContext = setup_loadingContext(loadingContext, runtimeContext, args)

        uri, tool_file_uri = resolve_tool_uri(
            args.workflow,
            resolver=loadingContext.resolver,
            fetcher_constructor=loadingContext.fetcher_constructor,
        )

        try_again_msg = "" if args.debug else ", try again with --debug for more information"

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
                    load_overrides(file_uri(os.path.abspath(args.overrides)), tool_file_uri)
                )

            loadingContext, workflowobj, uri = fetch_document(uri, loadingContext)

            if args.print_deps and loadingContext.loader:
                printdeps(workflowobj, loadingContext.loader, stdout, args.relative_deps, uri)
                return 0

            loadingContext, uri = resolve_and_validate_document(
                loadingContext,
                workflowobj,
                uri,
                preprocess_only=(args.print_pre or args.pack),
            )

            if loadingContext.loader is None:
                raise Exception("Impossible code path.")
            processobj, metadata = loadingContext.loader.resolve_ref(uri)
            processobj = cast(Union[CommentedMap, CommentedSeq], processobj)
            if args.pack:
                print(print_pack(loadingContext, uri), file=stdout)
                return 0

            if args.provenance and runtimeContext.research_obj:
                # Can't really be combined with args.pack at same time
                runtimeContext.research_obj.packed_workflow(print_pack(loadingContext, uri))

            if args.print_pre:
                json_dump(
                    processobj,
                    stdout,
                    indent=4,
                    sort_keys=True,
                    separators=(",", ": "),
                    default=str,
                )
                return 0

            try:
                tool = make_tool(uri, loadingContext)
            except GraphTargetMissingException as main_missing_exc:
                if args.validate:
                    logging.warning(
                        "File contains $graph of multiple objects and no default "
                        "process (#main). Validating all objects:"
                    )
                    for entry in workflowobj["$graph"]:
                        entry_id = entry["id"]
                        make_tool(entry_id, loadingContext)
                        print(f"{entry_id} is valid CWL.", file=stdout)
                else:
                    raise main_missing_exc

            if args.make_template:
                make_template(tool, stdout)
                return 0

            if args.validate:
                print(f"{args.workflow} is valid CWL.", file=stdout)
                return 0

            if args.print_rdf:
                print(
                    printrdf(tool, loadingContext.loader.ctx, args.rdf_serializer),
                    file=stdout,
                )
                return 0

            if args.print_dot:
                printdot(tool, loadingContext.loader.ctx, stdout)
                return 0

            if args.print_targets:
                print_targets(tool, stdout, loadingContext)
                return 0

            if args.target:
                ctool = choose_target(args, tool, loadingContext)
                if ctool is None:
                    return 1
                else:
                    tool = ctool

            elif args.single_step:
                ctool = choose_step(args, tool, loadingContext)
                if ctool is None:
                    return 1
                else:
                    tool = ctool

            elif args.single_process:
                ctool = choose_process(args, tool, loadingContext)
                if ctool is None:
                    return 1
                else:
                    tool = ctool

            if args.print_subgraph:
                if "name" in tool.tool:
                    del tool.tool["name"]
                json_dump(
                    tool.tool,
                    stdout,
                    indent=4,
                    sort_keys=True,
                    separators=(",", ": "),
                    default=str,
                )
                return 0

        except ValidationException as exc:
            _logger.error("Tool definition failed validation:\n%s", str(exc), exc_info=args.debug)
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

        runtimeContext.log_dir = args.log_dir

        runtimeContext.secret_store = getdefault(runtimeContext.secret_store, SecretStore())
        runtimeContext.make_fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)

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
                tfout, tfstatus = real_executor(tool.embedded_tool, tfjob_order, runtimeContext)
                if not tfout or tfstatus != "success":
                    raise WorkflowException("ProcessGenerator failed to generate workflow")
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
                    runtime_context=runtimeContext,
                )
            except SystemExit as err:
                if isinstance(err.code, int):
                    return err.code
                else:
                    _logger.debug("Non-integer SystemExit: %s", err.code)
                    return 1

            del args.workflow
            del args.job_order

            conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)  # str
            use_conda_dependencies = getattr(args, "beta_conda_dependencies", None)  # str

            if conf_file or use_conda_dependencies:
                runtimeContext.job_script_provider = DependenciesConfiguration(args)
            else:
                runtimeContext.find_default_container = functools.partial(
                    find_default_container,
                    default_container=runtimeContext.default_container,
                    use_biocontainers=args.beta_use_biocontainers,
                    container_image_cache_path=args.beta_dependencies_directory,
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

                if args.write_summary:
                    with open(args.write_summary, "w") as output_file:
                        json_dump(out, output_file, indent=4, ensure_ascii=False, default=str)
                else:
                    json_dump(out, stdout, indent=4, ensure_ascii=False, default=str)
                    if hasattr(stdout, "flush"):
                        stdout.flush()

            if status != "success":
                _logger.warning("Final process status is %s", status)
                return 1
            _logger.info("Final process status is %s", status)
            return 0

        except ValidationException as exc:
            _logger.error("Input object failed validation:\n%s", str(exc), exc_info=args.debug)
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
                research_obj.generate_snapshot(prov_deps(workflowobj, loadingContext.loader, uri))
            else:
                _logger.warning(
                    "Unable to generate provenance snapshot "
                    " due to missing loadingContext.loader."
                )
            if prov_log_handler is not None:
                # Stop logging so we won't half-log adding ourself to RO
                _logger.debug("[provenance] Closing provenance log file %s", prov_log_handler)
                _logger.removeHandler(prov_log_handler)
                # Ensure last log lines are written out
                prov_log_handler.flush()
                # Underlying WritableBagFile will add the tagfile to the manifest
                if prov_log_stream:
                    prov_log_stream.close()
                # Why not use prov_log_handler.stream ? That is not part of the
                # public API for logging.StreamHandler
                prov_log_handler.close()
            research_obj.close(args.provenance)

        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


def find_default_container(
    builder: HasReqsHints,
    default_container: Optional[str] = None,
    use_biocontainers: Optional[bool] = None,
    container_image_cache_path: Optional[str] = None,
) -> Optional[str]:
    """Find a container."""
    if not default_container and use_biocontainers:
        default_container = get_container_from_software_requirements(
            use_biocontainers, builder, container_image_cache_path
        )
    return default_container


def windows_check() -> None:
    """See if we are running on MS Windows and warn about the lack of support."""
    if os.name == "nt":
        warnings.warn(
            "The CWL reference runner (cwltool) no longer supports running "
            "CWL workflows natively on MS Windows as its previous MS Windows "
            "support was incomplete and untested. Instead, please see "
            "https://pypi.org/project/cwltool/#ms-windows-users "
            "for instructions on running cwltool via "
            "Windows Subsystem for Linux 2 (WSL2). If don't need to execute "
            "CWL documents, then you can ignore this warning, but please "
            "consider migrating to https://pypi.org/project/cwl-utils/ "
            "for your CWL document processing needs.",
            stacklevel=1,
        )


def run(*args: Any, **kwargs: Any) -> int:
    """Run cwltool."""
    windows_check()
    signal.signal(signal.SIGTERM, _signal_handler)
    retval = 1
    try:
        retval = main(*args, **kwargs)
    finally:
        _terminate_processes()
    return retval


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
