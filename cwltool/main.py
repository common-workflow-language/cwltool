#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function

import argparse
import collections
import functools
import json
import logging
import os
import sys
import warnings
from typing import (IO, Any, Callable, Dict, List, Text, Tuple,
                    Union, cast, Mapping, MutableMapping, Iterable)

import pkg_resources  # part of setuptools
import ruamel.yaml as yaml
import schema_salad.validate as validate
import six

from schema_salad.ref_resolver import Loader, file_uri, uri_file_path
from schema_salad.sourceline import strip_dup_lineno

from . import command_line_tool, workflow
from .argparser import arg_parser, generate_parser, DEFAULT_TMP_PREFIX
from .cwlrdf import printdot, printrdf
from .errors import UnsupportedRequirement, WorkflowException
from .executors import SingleJobExecutor, MultithreadedJobExecutor
from .load_tool import (FetcherConstructorType, resolve_tool_uri,
                        fetch_document, make_tool, validate_document, jobloaderctx,
                        resolve_overrides, load_overrides)
from .loghandler import defaultStreamHandler
from .mutation import MutationManager
from .pack import pack
from .pathmapper import (adjustDirObjs, trim_listing, visit_class)
from .process import (Process, normalizeFilesDirs,
                      scandeps, shortname, use_custom_schema,
                      use_standard_schema)
from .resolver import ga4gh_tool_registries, tool_resolver
from .software_requirements import (DependenciesConfiguration,
                                    get_container_from_software_requirements)
from .stdfsaccess import StdFsAccess
from .update import ALLUPDATES, UPDATES
from .utils import onWindows, windows_default_container_id

_logger = logging.getLogger("cwltool")


def single_job_executor(t,  # type: Process
                        job_order_object,  # type: Dict[Text, Any]
                        **kwargs  # type: Any
                        ):
    # type: (...) -> Tuple[Dict[Text, Any], Text]
    warnings.warn("Use of single_job_executor function is deprecated. "
                  "Use cwltool.executors.SingleJobExecutor class instead", DeprecationWarning)
    executor = SingleJobExecutor()
    return executor(t, job_order_object, **kwargs)


def generate_example_input(inptype):
    # type: (Union[Text, Dict[Text, Any]]) -> Any
    defaults = { 'null': 'null',
                 'Any': 'null',
                 'boolean': False,
                 'int': 0,
                 'long': 0,
                 'float': 0.1,
                 'double': 0.1,
                 'string': 'default_string',
                 'File': { 'class': 'File',
                           'path': 'default/file/path' },
                 'Directory': { 'class': 'Directory',
                                'path': 'default/directory/path' } }
    if (not isinstance(inptype, str) and
        not isinstance(inptype, collections.Mapping)
        and isinstance(inptype, collections.MutableSet)):
        if len(inptype) == 2 and 'null' in inptype:
            inptype.remove('null')
            return generate_example_input(inptype[0])
            # TODO: indicate that this input is optional
        else:
            raise Exception("multi-types other than optional not yet supported"
                            " for generating example input objects: %s"
                            % inptype)
    if isinstance(inptype, collections.Mapping) and 'type' in inptype:
        if inptype['type'] == 'array':
            return [ generate_example_input(inptype['items']) ]
        elif inptype['type'] == 'enum':
            return 'valid_enum_value'
            # TODO: list valid values in a comment
        elif inptype['type'] == 'record':
            record = {}
            for field in inptype['fields']:
                record[shortname(field['name'])] = generate_example_input(
                    field['type'])
            return record
    elif isinstance(inptype, str):
        return defaults.get(inptype, 'custom_type')
        # TODO: support custom types, complex arrays


def generate_input_template(tool):
    # type: (Process) -> Dict[Text, Any]
    template = {}
    for inp in tool.tool["inputs"]:
        name = shortname(inp["id"])
        inptype = inp["type"]
        template[name] = generate_example_input(inptype)
    return template


def load_job_order(args,   # type: argparse.Namespace
                   stdin,  # type: IO[Any]
                   fetcher_constructor,  # Fetcher
                   overrides,  # type: List[Dict[Text, Any]]
                   tool_file_uri  # type: Text
):
    # type: (...) -> Tuple[Dict[Text, Any], Text, Loader]

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
        input_basedir = args.basedir if args.basedir else os.path.abspath(os.path.dirname(job_order_file))
        job_order_object, _ = loader.resolve_ref(job_order_file, checklinks=False)

    if job_order_object and "http://commonwl.org/cwltool#overrides" in job_order_object:
        overrides.extend(resolve_overrides(job_order_object, file_uri(job_order_file), tool_file_uri))
        del job_order_object["http://commonwl.org/cwltool#overrides"]

    if not job_order_object:
        input_basedir = args.basedir if args.basedir else os.getcwd()

    return (job_order_object, input_basedir, loader)


def init_job_order(job_order_object,  # type: MutableMapping[Text, Any]
                   args,  # type: argparse.Namespace
                   t,     # type: Process
                   print_input_deps=False,  # type: bool
                   relative_deps=False,     # type: bool
                   stdout=sys.stdout,       # type: IO[Any]
                   make_fs_access=None,     # type: Callable[[Text], StdFsAccess]
                   loader=None,             # type: Loader
                   input_basedir=""         # type: Text
):
    # (...) -> Tuple[Dict[Text, Any], Text]

    if not job_order_object:
        namemap = {}  # type: Dict[Text, Text]
        records = []  # type: List[Text]
        toolparser = generate_parser(
            argparse.ArgumentParser(prog=args.workflow), t, namemap, records)
        if toolparser:
            if args.tool_help:
                toolparser.print_help()
                exit(0)
            cmd_line = vars(toolparser.parse_args(args.job_order))
            for record_name in records:
                record = {}
                record_items = {
                    k: v for k, v in six.iteritems(cmd_line)
                    if k.startswith(record_name)}
                for key, value in six.iteritems(record_items):
                    record[key[len(record_name) + 1:]] = value
                    del cmd_line[key]
                cmd_line[str(record_name)] = record

            if cmd_line["job_order"]:
                try:
                    job_order_object = cast(MutableMapping, loader.resolve_ref(cmd_line["job_order"])[0])
                except Exception as e:
                    _logger.error(Text(e), exc_info=args.debug)
                    return 1
            else:
                job_order_object = {"id": args.workflow}

            del cmd_line["job_order"]

            job_order_object.update({namemap[k]: v for k, v in cmd_line.items()})

            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(u"Parsed job order from command line: %s", json.dumps(job_order_object, indent=4))
        else:
            job_order_object = None

    for inp in t.tool["inputs"]:
        if "default" in inp and (not job_order_object or shortname(inp["id"]) not in job_order_object):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

    if not job_order_object and len(t.tool["inputs"]) > 0:
        if toolparser:
            print(u"\nOptions for {} ".format(args.workflow))
            toolparser.print_help()
        _logger.error("")
        _logger.error("Input object required, use --help for details")
        exit(1)

    if print_input_deps:
        printdeps(job_order_object, loader, stdout, relative_deps, "",
                  basedir=file_uri(str(input_basedir) + "/"))
        exit(0)

    def pathToLoc(p):
        if "location" not in p and "path" in p:
            p["location"] = p["path"]
            del p["path"]

    def addSizes(p):
        if 'location' in p:
            try:
                p["size"] = os.stat(p["location"][7:]).st_size  # strip off file://
            except OSError:
                pass
        elif 'contents' in p:
                p["size"] = len(p['contents'])
        else:
            return  # best effort

    ns = {}  # type: Dict[Text, Union[Dict[Any, Any], Text, Iterable[Text]]]
    ns.update(t.metadata.get("$namespaces", {}))
    ld = Loader(ns)

    def expand_formats(p):
        if "format" in p:
            p["format"] = ld.expand_url(p["format"], "")

    visit_class(job_order_object, ("File", "Directory"), pathToLoc)
    visit_class(job_order_object, ("File",), addSizes)
    visit_class(job_order_object, ("File",), expand_formats)
    adjustDirObjs(job_order_object, trim_listing)
    normalizeFilesDirs(job_order_object)

    if "cwl:tool" in job_order_object:
        del job_order_object["cwl:tool"]
    if "id" in job_order_object:
        del job_order_object["id"]

    return job_order_object


def makeRelative(base, ob):
    u = ob.get("location", ob.get("path"))
    if ":" in u.split("/")[0] and not u.startswith("file://"):
        pass
    else:
        if u.startswith("file://"):
            u = uri_file_path(u)
            ob["location"] = os.path.relpath(u, base)


def printdeps(obj, document_loader, stdout, relative_deps, uri, basedir=None):
    # type: (Mapping[Text, Any], Loader, IO[Any], bool, Text, Text) -> None
    deps = {"class": "File",
            "location": uri}  # type: Dict[Text, Any]

    def loadref(b, u):
        return document_loader.fetch(document_loader.fetcher.urljoin(b, u))

    sf = scandeps(
        basedir if basedir else uri, obj, {"$import", "run"},
        {"$include", "$schemas", "location"}, loadref)
    if sf:
        deps["secondaryFiles"] = sf

    if relative_deps:
        if relative_deps == "primary":
            base = basedir if basedir else os.path.dirname(uri_file_path(str(uri)))
        elif relative_deps == "cwd":
            base = os.getcwd()
        else:
            raise Exception(u"Unknown relative_deps %s" % relative_deps)

        visit_class(deps, ("File", "Directory"), functools.partial(makeRelative, base))

    stdout.write(json.dumps(deps, indent=4))


def print_pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Dict[Text, Any]) -> str
    packed = pack(document_loader, processobj, uri, metadata)
    if len(packed["$graph"]) > 1:
        return json.dumps(packed, indent=4)
    else:
        return json.dumps(packed["$graph"][0], indent=4)


def versionstring():
    # type: () -> Text
    pkg = pkg_resources.require("cwltool")
    if pkg:
        return u"%s %s" % (sys.argv[0], pkg[0].version)
    else:
        return u"%s %s" % (sys.argv[0], "unknown version")

def supportedCWLversions(enable_dev):
    # type: (bool) -> List[Text]
    # ALLUPDATES and UPDATES are dicts
    if enable_dev:
        versions = list(ALLUPDATES)
    else:
        versions = list(UPDATES)
    versions.sort()
    return versions

def main(argsl=None,  # type: List[str]
         args=None,  # type: argparse.Namespace
         executor=None,  # type: Callable[..., Tuple[Dict[Text, Any], Text]]
         makeTool=workflow.defaultMakeTool,  # type: Callable[..., Process]
         selectResources=None,  # type: Callable[[Dict[Text, int]], Dict[Text, int]]
         stdin=sys.stdin,  # type: IO[Any]
         stdout=sys.stdout,  # type: IO[Any]
         stderr=sys.stderr,  # type: IO[Any]
         versionfunc=versionstring,  # type: Callable[[], Text]
         job_order_object=None,  # type: MutableMapping[Text, Any]
         make_fs_access=StdFsAccess,  # type: Callable[[Text], StdFsAccess]
         fetcher_constructor=None,  # type: FetcherConstructorType
         resolver=tool_resolver,
         logger_handler=None,
         custom_schema_callback=None  # type: Callable[[], None]
         ):
    # type: (...) -> int

    _logger.removeHandler(defaultStreamHandler)
    if logger_handler:
        stderr_handler = logger_handler
    else:
        stderr_handler = logging.StreamHandler(stderr)
    _logger.addHandler(stderr_handler)
    try:
        if args is None:
            if argsl is None:
                argsl = sys.argv[1:]
            args = arg_parser().parse_args(argsl)

        # If On windows platform, A default Docker Container is Used if not explicitely provided by user
        if onWindows() and not args.default_container:
            # This docker image is a minimal alpine image with bash installed(size 6 mb). source: https://github.com/frol/docker-alpine-bash
            args.default_container = windows_default_container_id

        # If caller provided custom arguments, it may be not every expected
        # option is set, so fill in no-op defaults to avoid crashing when
        # dereferencing them in args.
        for k, v in six.iteritems({'print_deps': False,
                     'print_pre': False,
                     'print_rdf': False,
                     'print_dot': False,
                     'relative_deps': False,
                     'tmp_outdir_prefix': 'tmp',
                     'tmpdir_prefix': 'tmp',
                     'print_input_deps': False,
                     'cachedir': None,
                     'quiet': False,
                     'debug': False,
                     'timestamps': False,
                     'js_console': False,
                     'version': False,
                     'enable_dev': False,
                     'enable_ext': False,
                     'strict': True,
                     'skip_schemas': False,
                     'rdf_serializer': None,
                     'basedir': None,
                     'tool_help': False,
                     'workflow': None,
                     'job_order': None,
                     'pack': False,
                     'on_error': 'continue',
                     'relax_path_checks': False,
                     'validate': False,
                     'enable_ga4gh_tool_registry': False,
                     'ga4gh_tool_registries': [],
                     'find_default_container': None,
                                   'make_template': False,
                                   'overrides': None
        }):
            if not hasattr(args, k):
                setattr(args, k, v)

        if args.quiet:
            _logger.setLevel(logging.WARN)
        if args.debug:
            _logger.setLevel(logging.DEBUG)
        if args.timestamps:
            formatter = logging.Formatter("[%(asctime)s] %(message)s",
                                          "%Y-%m-%d %H:%M:%S")
            stderr_handler.setFormatter(formatter)

        if args.version:
            print(versionfunc())
            return 0
        else:
            _logger.info(versionfunc())

        if args.print_supported_versions:
            print("\n".join(supportedCWLversions(args.enable_dev)))
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

        uri, tool_file_uri = resolve_tool_uri(args.workflow,
                                              resolver=resolver,
                                              fetcher_constructor=fetcher_constructor)

        overrides = []  # type: List[Dict[Text, Any]]

        try:
            job_order_object, input_basedir, jobloader = load_job_order(args,
                                                                        stdin,
                                                                        fetcher_constructor,
                                                                        overrides,
                                                                        tool_file_uri)
        except Exception as e:
            _logger.error(Text(e), exc_info=args.debug)

        if args.overrides:
            overrides.extend(load_overrides(file_uri(os.path.abspath(args.overrides)), tool_file_uri))

        try:
            document_loader, workflowobj, uri = fetch_document(uri, resolver=resolver,
                                                               fetcher_constructor=fetcher_constructor)

            if args.print_deps:
                printdeps(workflowobj, document_loader, stdout, args.relative_deps, uri)
                return 0

            document_loader, avsc_names, processobj, metadata, uri \
                = validate_document(document_loader, workflowobj, uri,
                                    enable_dev=args.enable_dev, strict=args.strict,
                                    preprocess_only=args.print_pre or args.pack,
                                    fetcher_constructor=fetcher_constructor,
                                    skip_schemas=args.skip_schemas,
                                    overrides=overrides)

            if args.print_pre:
                stdout.write(json.dumps(processobj, indent=4))
                return 0

            overrides.extend(metadata.get("cwltool:overrides", []))

            conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)  # Text
            use_conda_dependencies = getattr(args, "beta_conda_dependencies", None)  # Text

            make_tool_kwds = vars(args)

            job_script_provider = None  # type: Callable[[Any, List[str]], Text]
            if conf_file or use_conda_dependencies:
                dependencies_configuration = DependenciesConfiguration(args)  # type: DependenciesConfiguration
                make_tool_kwds["job_script_provider"] = dependencies_configuration

            make_tool_kwds["find_default_container"] = functools.partial(find_default_container, args)
            make_tool_kwds["overrides"] = overrides

            tool = make_tool(document_loader, avsc_names, metadata, uri,
                             makeTool, make_tool_kwds)
            if args.make_template:
                yaml.safe_dump(generate_input_template(tool), sys.stdout,
                               default_flow_style=False, indent=4,
                               block_seq_indent=2)
                return 0

            if args.validate:
                _logger.info("Tool definition is valid")
                return 0

            if args.pack:
                stdout.write(print_pack(document_loader, processobj, uri, metadata))
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
                u"I'm sorry, I couldn't load this CWL file%s",
                ", try again with --debug for more information.\nThe error was: "
                "%s" % exc if not args.debug else ".  The error was:",
                exc_info=args.debug)
            return 1

        if isinstance(tool, int):
            return tool

        # If on MacOS platform, TMPDIR must be set to be under one of the shared volumes in Docker for Mac
        # More info: https://dockstore.org/docs/faq
        if sys.platform == "darwin":
            tmp_prefix = "tmp_outdir_prefix"
            default_mac_path = "/private/tmp/docker_tmp"
            if getattr(args, tmp_prefix) and getattr(args, tmp_prefix) == DEFAULT_TMP_PREFIX:
                setattr(args, tmp_prefix, default_mac_path)

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if getattr(args, dirprefix) and getattr(args, dirprefix) != DEFAULT_TMP_PREFIX:
                sl = "/" if getattr(args, dirprefix).endswith("/") or dirprefix == "cachedir" else ""
                setattr(args, dirprefix,
                        os.path.abspath(getattr(args, dirprefix)) + sl)
                if not os.path.exists(os.path.dirname(getattr(args, dirprefix))):
                    try:
                        os.makedirs(os.path.dirname(getattr(args, dirprefix)))
                    except Exception as e:
                        _logger.error("Failed to create directory: %s", e)
                        return 1

        if args.cachedir:
            if args.move_outputs == "move":
                setattr(args, 'move_outputs', "copy")
            setattr(args, "tmp_outdir_prefix", args.cachedir)

        try:
            job_order_object = init_job_order(job_order_object, args, tool,
                                              print_input_deps=args.print_input_deps,
                                              relative_deps=args.relative_deps,
                                              stdout=stdout,
                                              make_fs_access=make_fs_access,
                                              loader=jobloader,
                                              input_basedir=input_basedir)
        except SystemExit as e:
            return e.code

        if not executor:
            if args.parallel:
                executor = MultithreadedJobExecutor()
            else:
                executor = SingleJobExecutor()

        if isinstance(job_order_object, int):
            return job_order_object

        try:
            setattr(args, 'basedir', input_basedir)
            del args.workflow
            del args.job_order
            (out, status) = executor(tool, job_order_object,
                                     logger=_logger,
                                     makeTool=makeTool,
                                     select_resources=selectResources,
                                     make_fs_access=make_fs_access,
                                     **vars(args))

            # This is the workflow output, it needs to be written
            if out is not None:

                def locToPath(p):
                    for field in ("path", "nameext", "nameroot", "dirname"):
                        if field in p:
                            del p[field]
                    if p["location"].startswith("file://"):
                        p["path"] = uri_file_path(p["location"])

                visit_class(out, ("File", "Directory"), locToPath)

                # Unsetting the Generation fron final output object
                visit_class(out,("File",), MutationManager().unset_generation)

                if isinstance(out, six.string_types):
                    stdout.write(out)
                else:
                    stdout.write(json.dumps(out, indent=4))
                stdout.write("\n")
                stdout.flush()

            if status != "success":
                _logger.warning(u"Final process status is %s", status)
                return 1
            else:
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
                u"Workflow error, try again with --debug for more "
                "information:\n%s", strip_dup_lineno(six.text_type(exc)), exc_info=args.debug)
            return 1
        except Exception as exc:
            _logger.error(
                u"Unhandled error, try again with --debug for more information:\n"
                "  %s", exc, exc_info=args.debug)
            return 1

    finally:
        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


def find_default_container(args, builder):
    default_container = None
    if args.default_container:
        default_container = args.default_container
    elif args.beta_use_biocontainers:
        default_container = get_container_from_software_requirements(args, builder)

    return default_container


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
