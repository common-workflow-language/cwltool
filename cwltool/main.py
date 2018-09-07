#!/usr/bin/env python
"""Entry point for cwltool."""
from __future__ import absolute_import, print_function

import argparse
import collections
import copy
import functools
import io
import logging
import os
import signal
import sys
from codecs import StreamWriter, getwriter  # pylint: disable=unused-import
from typing import (IO, Any, Callable, Dict, Iterable, List, Mapping,
                    MutableMapping, MutableSequence, Optional, TextIO, Tuple,
                    Union, cast)

import pkg_resources  # part of setuptools
from ruamel import yaml
from schema_salad import validate
from schema_salad.ref_resolver import Loader, file_uri, uri_file_path
from schema_salad.sourceline import strip_dup_lineno
from six import string_types, iteritems, PY3
from typing_extensions import Text
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import command_line_tool, workflow
from .argparser import arg_parser, generate_parser, get_default_args
from .builder import HasReqsHints  # pylint: disable=unused-import
from .context import LoadingContext, RuntimeContext, getdefault
from .cwlrdf import printdot, printrdf
from .errors import UnsupportedRequirement, WorkflowException
from .executors import MultithreadedJobExecutor, SingleJobExecutor
from .load_tool import (FetcherConstructorType,  # pylint: disable=unused-import
                        fetch_document, jobloaderctx, load_overrides,
                        make_tool, resolve_overrides, resolve_tool_uri,
                        validate_document)
from .loghandler import _logger, defaultStreamHandler
from .mutation import MutationManager
from .pack import pack
from .pathmapper import (adjustDirObjs, normalizeFilesDirs, trim_listing,
                         visit_class)
from .process import (Process, add_sizes,  # pylint: disable=unused-import
                      scandeps, shortname, use_custom_schema,
                      use_standard_schema)
from .provenance import ResearchObject
from .resolver import ga4gh_tool_registries, tool_resolver
from .secrets import SecretStore
from .software_requirements import (DependenciesConfiguration,
                                    get_container_from_software_requirements)
from .stdfsaccess import StdFsAccess
from .update import ALLUPDATES, UPDATES
from .utils import (DEFAULT_TMP_PREFIX, json_dumps, onWindows,
                    processes_to_kill, versionstring,
                    windows_default_container_id)


def _terminate_processes():
    # type: () -> None
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


def _signal_handler(signum, _):
    # type: (int, Any) -> None
    """Kill all spawned processes and exit.

    Note that it's possible for another thread to spawn a process after
    all processes have been killed, but before Python exits.

    Refer to the docstring for _terminate_processes() for other caveats.
    """
    _terminate_processes()
    sys.exit(signum)


def generate_example_input(inptype,     # type: Any
                           default      # type: Optional[Any]
                          ):  # type: (...) -> Tuple[Any, Text]
    """Converts a single input schema into an example."""
    example = None
    comment = u""
    defaults = {u'null': 'null',
                u'Any': 'null',
                u'boolean': False,
                u'int': 0,
                u'long': 0,
                u'float': 0.1,
                u'double': 0.1,
                u'string': 'a_string',
                u'File': yaml.comments.CommentedMap([
                    ('class', 'File'), ('path', 'a/file/path')]),
                u'Directory': yaml.comments.CommentedMap([
                    ('class', 'Directory'), ('path', 'a/directory/path')])
               }  # type: Dict[Text, Any]
    if isinstance(inptype, collections.MutableSequence):
        optional = False
        if 'null' in inptype:
            inptype.remove('null')
            optional = True
        if len(inptype) == 1:
            example, comment = generate_example_input(inptype[0], default)
            if optional:
                if comment:
                    comment = u"{} (optional)".format(comment)
                else:
                    comment = u"optional"
        else:
            example = yaml.comments.CommentedSeq()
            for index, entry in enumerate(inptype):
                value, e_comment = generate_example_input(entry, default)
                example.append(value)
                example.yaml_add_eol_comment(e_comment, index)
            if optional:
                comment = u"optional"
    elif isinstance(inptype, collections.Mapping) and 'type' in inptype:
        if inptype['type'] == 'array':
            if len(inptype['items']) == 1 and 'type' in inptype['items'][0] \
                    and inptype['items'][0]['type'] == 'enum':
                # array of just an enum then list all the options
                example = inptype['items'][0]['symbols']
                if 'name' in inptype['items'][0]:
                    comment = u'array of type "{}".'.format(inptype['items'][0]['name'])
            else:
                value, comment = generate_example_input(inptype['items'], None)
                comment = u"array of " + comment
                if len(inptype['items']) == 1:
                    example = [value]
                else:
                    example = value
            if default:
                example = default
        elif inptype['type'] == 'enum':
            if default:
                example = default
            elif 'default' in inptype:
                example = inptype['default']
            elif len(inptype['symbols']) == 1:
                example = inptype['symbols'][0]
            else:
                example = '{}_enum_value'.format(inptype.get('name', 'valid'))
            comment = u'enum; valid values: "{}"'.format(
                '", "'.join(inptype['symbols']))
        elif inptype['type'] == 'record':
            example = yaml.comments.CommentedMap()
            if 'name' in inptype:
                comment = u'"{}" record type.'.format(inptype['name'])
            for field in inptype['fields']:
                value, f_comment = generate_example_input(field['type'], None)
                example.insert(0, shortname(field['name']), value, f_comment)
        elif 'default' in inptype:
            example = inptype['default']
            comment = u'default value of type "{}".'.format(inptype['type'])
        else:
            example = defaults.get(inptype['type'], Text(inptype))
            comment = u'type "{}".'.format(inptype['type'])
    else:
        if not default:
            example = defaults.get(Text(inptype), Text(inptype))
            comment = u'type "{}"'.format(inptype)
        else:
            example = default
            comment = u'default value of type "{}".'.format(inptype)
    return example, comment

def realize_input_schema(input_types,  # type: MutableSequence[Dict[Text, Any]]
                         schema_defs   # type: Dict[Text, Any]
                        ):  # type: (...) -> MutableSequence[Dict[Text, Any]]
    """Replace references to named typed with the actual types."""
    for index, entry in enumerate(input_types):
        if isinstance(entry, string_types):
            if '#' in entry:
                _, input_type_name = entry.split('#')
            else:
                input_type_name = entry
            if input_type_name in schema_defs:
                entry = input_types[index] = schema_defs[input_type_name]
        if isinstance(entry, collections.Mapping):
            if isinstance(entry['type'], string_types) and '#' in entry['type']:
                _, input_type_name = entry['type'].split('#')
                if input_type_name in schema_defs:
                    input_types[index]['type'] = realize_input_schema(
                        schema_defs[input_type_name], schema_defs)
            if isinstance(entry['type'], collections.MutableSequence):
                input_types[index]['type'] = realize_input_schema(
                    entry['type'], schema_defs)
            if isinstance(entry['type'], collections.Mapping):
                input_types[index]['type'] = realize_input_schema(
                    [input_types[index]['type']], schema_defs)
            if entry['type'] == 'array':
                items = entry['items'] if \
                    not isinstance(entry['items'], string_types) else [entry['items']]
                input_types[index]['items'] = realize_input_schema(items, schema_defs)
            if entry['type'] == 'record':
                input_types[index]['fields'] = realize_input_schema(
                    entry['fields'], schema_defs)
    return input_types

def generate_input_template(tool):
    # type: (Process) -> Dict[Text, Any]
    """Generate an example input object for the given CWL process."""
    template = yaml.comments.CommentedMap()
    for inp in realize_input_schema(tool.tool["inputs"], tool.schemaDefs):
        name = shortname(inp["id"])
        value, comment = generate_example_input(
            inp['type'], inp.get('default', None))
        template.insert(0, name, value, comment)
    return template

def load_job_order(args,                 # type: argparse.Namespace
                   stdin,                # type: IO[Any]
                   fetcher_constructor,  # Fetcher
                   overrides_list,       # type: List[Dict[Text, Any]]
                   tool_file_uri         # type: Text
                  ):  # type: (...) -> Tuple[MutableMapping[Text, Any], Text, Loader]

    job_order_object = None

    _jobloaderctx = jobloaderctx.copy()
    loader = Loader(_jobloaderctx, fetcher_constructor=fetcher_constructor)  # type: ignore

    if len(args.job_order) == 1 and args.job_order[0][0] != "-":
        job_order_file = args.job_order[0]
    elif len(args.job_order) == 1 and args.job_order[0] == "-":
        job_order_object = yaml.round_trip_load(stdin)
        job_order_object, _ = loader.resolve_all(job_order_object, file_uri(os.getcwd()) + "/")
    else:
        job_order_file = None

    if job_order_object:
        input_basedir = args.basedir if args.basedir else os.getcwd()
    elif job_order_file:
        input_basedir = args.basedir if args.basedir \
            else os.path.abspath(os.path.dirname(job_order_file))
        job_order_object, _ = loader.resolve_ref(job_order_file, checklinks=False)

    if job_order_object and "http://commonwl.org/cwltool#overrides" in job_order_object:
        overrides_list.extend(
            resolve_overrides(job_order_object, file_uri(job_order_file), tool_file_uri))
        del job_order_object["http://commonwl.org/cwltool#overrides"]

    if not job_order_object:
        input_basedir = args.basedir if args.basedir else os.getcwd()

    return (job_order_object, input_basedir, loader)


def init_job_order(job_order_object,        # type: Optional[MutableMapping[Text, Any]]
                   args,                    # type: argparse.Namespace
                   process,                 # type: Process
                   loader,                  # type: Loader
                   stdout,                  # type: Union[TextIO, StreamWriter]
                   print_input_deps=False,  # type: bool
                   relative_deps=False,     # type: bool
                   make_fs_access=StdFsAccess,  # type: Callable[[Text], StdFsAccess]
                   input_basedir="",        # type: Text
                   secret_store=None        # type: SecretStore
                  ):  # type: (...) -> MutableMapping[Text, Any]
    secrets_req, _ = process.get_requirement("http://commonwl.org/cwltool#Secrets")
    if not job_order_object:
        namemap = {}  # type: Dict[Text, Text]
        records = []  # type: List[Text]
        toolparser = generate_parser(
            argparse.ArgumentParser(prog=args.workflow), process, namemap, records)
        if toolparser:
            if args.tool_help:
                toolparser.print_help()
                exit(0)
            cmd_line = vars(toolparser.parse_args(args.job_order))
            for record_name in records:
                record = {}
                record_items = {
                    k: v for k, v in iteritems(cmd_line)
                    if k.startswith(record_name)}
                for key, value in iteritems(record_items):
                    record[key[len(record_name) + 1:]] = value
                    del cmd_line[key]
                cmd_line[str(record_name)] = record

            if cmd_line["job_order"]:
                try:
                    job_order_object = cast(
                        MutableMapping, loader.resolve_ref(cmd_line["job_order"])[0])
                except Exception as err:
                    _logger.error(Text(err), exc_info=args.debug)
                    exit(1)
            else:
                job_order_object = {"id": args.workflow}

            del cmd_line["job_order"]

            job_order_object.update({namemap[k]: v for k, v in cmd_line.items()})

            if secret_store and secrets_req:
                secret_store.store(
                    [shortname(sc) for sc in secrets_req["secrets"]], job_order_object)

            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(u"Parsed job order from command line: %s",
                              json_dumps(job_order_object, indent=4))
        else:
            job_order_object = None

    for inp in process.tool["inputs"]:
        if "default" in inp and (
                not job_order_object or shortname(inp["id"]) not in job_order_object):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

    if not job_order_object:
        if process.tool["inputs"]:
            if toolparser:
                print(u"\nOptions for {} ".format(args.workflow))
                toolparser.print_help()
            _logger.error("")
            _logger.error("Input object required, use --help for details")
            exit(1)
        else:
            job_order_object = {}

    if print_input_deps:
        printdeps(job_order_object, loader, stdout, relative_deps, "",
                  basedir=file_uri(str(input_basedir) + "/"))
        exit(0)

    def path_to_loc(p):
        if "location" not in p and "path" in p:
            p["location"] = p["path"]
            del p["path"]

    ns = {}  # type: Dict[Text, Union[Dict[Any, Any], Text, Iterable[Text]]]
    ns.update(process.metadata.get("$namespaces", {}))
    ld = Loader(ns)

    def expand_formats(p):
        if "format" in p:
            p["format"] = ld.expand_url(p["format"], "")

    visit_class(job_order_object, ("File", "Directory"), path_to_loc)
    visit_class(job_order_object, ("File",), functools.partial(add_sizes, make_fs_access(input_basedir)))
    visit_class(job_order_object, ("File",), expand_formats)
    adjustDirObjs(job_order_object, trim_listing)
    normalizeFilesDirs(job_order_object)

    if secret_store and secrets_req:
        secret_store.store(
            [shortname(sc) for sc in secrets_req["secrets"]], job_order_object)

    if "cwl:tool" in job_order_object:
        del job_order_object["cwl:tool"]
    if "id" in job_order_object:
        del job_order_object["id"]
    return job_order_object



def make_relative(base, obj):
    """Relativize the location URI of a File or Directory object."""
    uri = obj.get("location", obj.get("path"))
    if ":" in uri.split("/")[0] and not uri.startswith("file://"):
        pass
    else:
        if uri.startswith("file://"):
            uri = uri_file_path(uri)
            obj["location"] = os.path.relpath(uri, base)


def printdeps(obj,              # type: Optional[Mapping[Text, Any]]
              document_loader,  # type: Loader
              stdout,           # type: Union[TextIO, StreamWriter]
              relative_deps,    # type: bool
              uri,              # type: Text
              prov_args=None,   # type: Any
              basedir=None      # type: Text
             ):  # type: (...) -> Tuple[Optional[Dict[Text, Any]], Optional[Dict[Text, Any]]]
    """Print a JSON representation of the dependencies of the CWL document."""
    deps = {"class": "File", "location": uri}  # type: Dict[Text, Any]

    def loadref(base, uri):
        return document_loader.fetch(document_loader.fetcher.urljoin(base, uri))

    sfs = scandeps(
        basedir if basedir else uri, obj, {"$import", "run"},
        {"$include", "$schemas", "location"}, loadref)
    if sfs:
        deps["secondaryFiles"] = sfs

    if relative_deps:
        if relative_deps == "primary":
            base = basedir if basedir else os.path.dirname(uri_file_path(str(uri)))
        elif relative_deps == "cwd":
            base = os.getcwd()
        else:
            raise Exception(u"Unknown relative_deps %s" % relative_deps)
        absdeps = copy.deepcopy(deps)
        visit_class(deps, ("File", "Directory"), functools.partial(make_relative, base))
    if prov_args:
        return (deps, absdeps)
    stdout.write(json_dumps(deps, indent=4))
    return (None, None)

def print_pack(document_loader,  # type: Loader
               processobj,       # type: Union[Dict[Text, Any], List[Dict[Text, Any]]]
               uri,              # type: Text
               metadata          # type: Dict[Text, Any]
              ):  # type (...) -> Text
    """Return a CWL serialization of the CWL document in JSON."""
    packed = pack(document_loader, processobj, uri, metadata)
    if len(packed["$graph"]) > 1:
        return json_dumps(packed, indent=4)
    return json_dumps(packed["$graph"][0], indent=4)


def supported_cwl_versions(enable_dev):  # type: (bool) -> List[Text]
    # ALLUPDATES and UPDATES are dicts
    if enable_dev:
        versions = list(ALLUPDATES)
    else:
        versions = list(UPDATES)
    versions.sort()
    return versions

def main(argsl=None,                   # type: List[str]
         args=None,                    # type: argparse.Namespace
         job_order_object=None,        # type: MutableMapping[Text, Any]
         stdin=sys.stdin,              # type: IO[Any]
         stdout=None,                  # type: Union[TextIO, StreamWriter]
         stderr=sys.stderr,            # type: IO[Any]
         versionfunc=versionstring,    # type: Callable[[], Text]
         logger_handler=None,          #
         custom_schema_callback=None,  # type: Callable[[], None]
         executor=None,                # type: Callable[..., Tuple[Dict[Text, Any], Text]]
         loadingContext=None,          # type: LoadingContext
         runtimeContext=None           # type: RuntimeContext
        ):  # type: (...) -> int
    if not stdout:  # force UTF-8 even if the console is configured differently
        if (hasattr(sys.stdout, "encoding")  # type: ignore
                and sys.stdout.encoding != 'UTF-8'):  # type: ignore
            if PY3 and hasattr(sys.stdout, "detach"):
                stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            else:
                stdout = getwriter('utf-8')(sys.stdout)  # type: ignore
        else:
            stdout = cast(TextIO, sys.stdout)  # type: ignore

    _logger.removeHandler(defaultStreamHandler)
    if logger_handler:
        stderr_handler = logger_handler
    else:
        stderr_handler = logging.StreamHandler(stderr)
    _logger.addHandler(stderr_handler)
    # pre-declared for finally block
    workflowobj = None
    try:
        if args is None:
            if argsl is None:
                argsl = sys.argv[1:]
            args = arg_parser().parse_args(argsl)

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
        for key, val in iteritems(get_default_args()):
            if not hasattr(args, key):
                setattr(args, key, val)

        rdflib_logger = logging.getLogger("rdflib.term")
        rdflib_logger.addHandler(stderr_handler)
        rdflib_logger.setLevel(logging.ERROR)
        if args.quiet:
            _logger.setLevel(logging.WARN)
        if runtimeContext.debug:
            _logger.setLevel(logging.DEBUG)
            rdflib_logger.setLevel(logging.DEBUG)
        if args.timestamps:
            formatter = logging.Formatter("[%(asctime)s] %(message)s",
                                          "%Y-%m-%d %H:%M:%S")
            stderr_handler.setFormatter(formatter)

        if args.version:
            print(versionfunc())
            return 0
        _logger.info(versionfunc())

        if args.print_supported_versions:
            print("\n".join(supported_cwl_versions(args.enable_dev)))
            return 0

        if not args.workflow:
            if os.path.isfile("CWLFile"):
                setattr(args, "workflow", "CWLFile")
            else:
                _logger.error("")
                _logger.error("CWL document required, no input file was provided")
                arg_parser().print_help()
                return 1
        if args.relax_path_checks:
            command_line_tool.ACCEPTLIST_RE = command_line_tool.ACCEPTLIST_EN_RELAXED_RE

        if args.ga4gh_tool_registries:
            ga4gh_tool_registries[:] = args.ga4gh_tool_registries
        if not args.enable_ga4gh_tool_registry:
            del ga4gh_tool_registries[:]

        if custom_schema_callback:
            custom_schema_callback()
        elif args.enable_ext:
            res = pkg_resources.resource_stream(__name__, 'extensions.yml')
            use_custom_schema("v1.0", "http://commonwl.org/cwltool", res.read())
            res.close()
        else:
            use_standard_schema("v1.0")
        if args.provenance:
            if not args.compute_checksum:
                _logger.error("--provenance incompatible with --no-compute-checksum")
                return 1
            runtimeContext.research_obj = ResearchObject(
                temp_prefix_ro=args.tmpdir_prefix, orcid=args.orcid,
                full_name=args.cwl_full_name)

        if loadingContext is None:
            loadingContext = LoadingContext(vars(args))
        else:
            loadingContext = loadingContext.copy()
        loadingContext.research_obj = runtimeContext.research_obj
        loadingContext.disable_js_validation = \
            args.disable_js_validation or (not args.do_validate)
        loadingContext.construct_tool_object = getdefault(
            loadingContext.construct_tool_object, workflow.default_make_tool)
        loadingContext.resolver = getdefault(loadingContext.resolver, tool_resolver)

        uri, tool_file_uri = resolve_tool_uri(
            args.workflow, resolver=loadingContext.resolver,
            fetcher_constructor=loadingContext.fetcher_constructor)

        try_again_msg = "" if args.debug else ", try again with --debug for more information"

        try:
            job_order_object, input_basedir, jobloader = load_job_order(
                args, stdin, loadingContext.fetcher_constructor,
                loadingContext.overrides_list, tool_file_uri)

            if args.overrides:
                loadingContext.overrides_list.extend(load_overrides(
                    file_uri(os.path.abspath(args.overrides)), tool_file_uri))

            document_loader, workflowobj, uri = fetch_document(
                uri, resolver=loadingContext.resolver,
                fetcher_constructor=loadingContext.fetcher_constructor)

            if args.print_deps:
                printdeps(workflowobj, document_loader, stdout, args.relative_deps, uri)
                return 0

            document_loader, avsc_names, processobj, metadata, uri \
                = validate_document(document_loader, workflowobj, uri,
                                    enable_dev=loadingContext.enable_dev,
                                    strict=loadingContext.strict,
                                    preprocess_only=(args.print_pre or args.pack),
                                    fetcher_constructor=loadingContext.fetcher_constructor,
                                    skip_schemas=args.skip_schemas,
                                    overrides=loadingContext.overrides_list,
                                    do_validate=loadingContext.do_validate)
            if args.pack:
                stdout.write(print_pack(document_loader, processobj, uri, metadata))
                return 0
            if args.provenance and runtimeContext.research_obj:
                # Can't really be combined with args.pack at same time
                runtimeContext.research_obj.packed_workflow(
                    print_pack(document_loader, processobj, uri, metadata))

            if args.print_pre:
                stdout.write(json_dumps(processobj, indent=4))
                return 0

            loadingContext.overrides_list.extend(metadata.get("cwltool:overrides", []))

            tool = make_tool(document_loader, avsc_names,
                             metadata, uri, loadingContext)
            if args.make_template:
                def my_represent_none(self, data):  # pylint: disable=unused-argument
                    """Force clean representation of 'null'."""
                    return self.represent_scalar(u'tag:yaml.org,2002:null', u'null')
                yaml.RoundTripRepresenter.add_representer(type(None), my_represent_none)
                yaml.round_trip_dump(
                    generate_input_template(tool), sys.stdout,
                    default_flow_style=False, indent=4, block_seq_indent=2)
                return 0

            if args.validate:
                print("{} is valid CWL.".format(args.workflow))
                return 0

            if args.print_rdf:
                stdout.write(printrdf(tool, document_loader.ctx, args.rdf_serializer))
                return 0

            if args.print_dot:
                printdot(tool, document_loader.ctx, stdout)
                return 0

        except (validate.ValidationException) as exc:
            _logger.error(u"Tool definition failed validation:\n%s", exc,
                          exc_info=args.debug)
            return 1
        except (RuntimeError, WorkflowException) as exc:
            _logger.error(u"Tool definition failed initialization:\n%s", exc,
                          exc_info=args.debug)
            return 1
        except Exception as exc:
            _logger.error(
                u"I'm sorry, I couldn't load this CWL file%s.\nThe error was: %s",
                try_again_msg,
                exc if not args.debug else "",
                exc_info=args.debug)
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

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if getattr(runtimeContext, dirprefix) and getattr(runtimeContext, dirprefix) != DEFAULT_TMP_PREFIX:
                sl = "/" if getattr(runtimeContext, dirprefix).endswith("/") or dirprefix == "cachedir" \
                    else ""
                setattr(runtimeContext, dirprefix,
                        os.path.abspath(getattr(runtimeContext, dirprefix)) + sl)
                if not os.path.exists(os.path.dirname(getattr(runtimeContext, dirprefix))):
                    try:
                        os.makedirs(os.path.dirname(getattr(runtimeContext, dirprefix)))
                    except Exception as e:
                        _logger.error("Failed to create directory: %s", e)
                        return 1

        if args.cachedir:
            if args.move_outputs == "move":
                runtimeContext.move_outputs = "copy"
            runtimeContext.tmp_outdir_prefix = args.cachedir

        runtimeContext.secret_store = getdefault(runtimeContext.secret_store, SecretStore())
        runtimeContext.make_fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)
        try:
            initialized_job_order_object = init_job_order(
                job_order_object, args, tool, jobloader, stdout,
                print_input_deps=args.print_input_deps,
                relative_deps=args.relative_deps,
                make_fs_access=runtimeContext.make_fs_access,
                input_basedir=input_basedir,
                secret_store=runtimeContext.secret_store)
        except SystemExit as err:
            return err.code

        if not executor:
            if args.parallel:
                executor = MultithreadedJobExecutor()
                runtimeContext.select_resources = executor.select_resources
            else:
                executor = SingleJobExecutor()
        assert executor is not None

        try:
            runtimeContext.basedir = input_basedir
            del args.workflow
            del args.job_order

            conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)  # Text
            use_conda_dependencies = getattr(args, "beta_conda_dependencies", None)  # Text

            if conf_file or use_conda_dependencies:
                runtimeContext.job_script_provider = DependenciesConfiguration(args)
            else:
                runtimeContext.find_default_container = functools.partial(
                    find_default_container,
                    default_container=runtimeContext.default_container,
                    use_biocontainers=args.beta_use_biocontainers)

            (out, status) = executor(tool,
                                     initialized_job_order_object,
                                     runtimeContext,
                                     logger=_logger)

            if out is not None:
                if runtimeContext.research_obj:
                    runtimeContext.research_obj.create_job(out, None, True)
                def loc_to_path(obj):
                    for field in ("path", "nameext", "nameroot", "dirname"):
                        if field in obj:
                            del obj[field]
                    if obj["location"].startswith("file://"):
                        obj["path"] = uri_file_path(obj["location"])

                visit_class(out, ("File", "Directory"), loc_to_path)

                # Unsetting the Generation from final output object
                visit_class(out, ("File", ), MutationManager().unset_generation)

                if isinstance(out, string_types):
                    stdout.write(out)
                else:
                    stdout.write(json_dumps(out, indent=4,  # type: ignore
                                            ensure_ascii=False))
                stdout.write("\n")
                if hasattr(stdout, "flush"):
                    stdout.flush()  # type: ignore

            if status != "success":
                _logger.warning(u"Final process status is %s", status)
                return 1
            _logger.info(u"Final process status is %s", status)
            return 0

        except (validate.ValidationException) as exc:
            _logger.error(u"Input object failed validation:\n%s", exc,
                          exc_info=args.debug)
            return 1
        except UnsupportedRequirement as exc:
            _logger.error(
                u"Workflow or tool uses unsupported feature:\n%s", exc,
                exc_info=args.debug)
            return 33
        except WorkflowException as exc:
            _logger.error(
                u"Workflow error%s:\n%s", try_again_msg, strip_dup_lineno(Text(exc)),
                exc_info=args.debug)
            return 1
        except Exception as exc:
            _logger.error(
                u"Unhandled error%s:\n  %s", try_again_msg, exc, exc_info=args.debug)
            return 1

    finally:
        if args and runtimeContext and runtimeContext.research_obj \
                and args.rm_tmpdir and workflowobj:
            #adding all related cwl files to RO
            prov_dependencies = printdeps(
                workflowobj, document_loader, stdout, args.relative_deps, uri,
                runtimeContext.research_obj)
            prov_dep = prov_dependencies[1]
            assert prov_dep
            runtimeContext.research_obj.generate_snapshot(prov_dep)

            runtimeContext.research_obj.close(args.provenance)

        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


def find_default_container(builder,                  # type: HasReqsHints
                           default_container=None,   # type: Text
                           use_biocontainers=None,  # type: bool
                          ):  # type: (...) -> Optional[Text]
    """Default finder for default containers."""
    if not default_container and use_biocontainers:
        default_container = get_container_from_software_requirements(
            use_biocontainers, builder)
    return default_container


def run(*args, **kwargs):
    # type: (...) -> None
    """Run cwltool."""
    signal.signal(signal.SIGTERM, _signal_handler)
    try:
        sys.exit(main(*args, **kwargs))
    finally:
        _terminate_processes()


if __name__ == "__main__":
    run(sys.argv[1:])
