#!/usr/bin/env python
from __future__ import absolute_import, print_function

import argparse
import codecs
from codecs import StreamWriter  # pylint: disable=unused-import
import collections
import copy
import functools
import io
import logging
import os
import sys
import warnings
from typing import (IO, Any, Callable, Dict,  # pylint: disable=unused-import
                    Iterable, List, Mapping, MutableMapping, Optional, Text,
                    TextIO, Tuple, Union, cast)

import pkg_resources  # part of setuptools
import ruamel.yaml as yaml
import schema_salad.validate as validate
from schema_salad.ref_resolver import Loader, file_uri, uri_file_path
from schema_salad.sourceline import strip_dup_lineno
import six
from six import string_types

from . import command_line_tool, workflow
from .argparser import arg_parser, generate_parser, get_default_args
from .cwlrdf import printdot, printrdf
from .errors import UnsupportedRequirement, WorkflowException
from .executors import MultithreadedJobExecutor, SingleJobExecutor
from .load_tool import (  # pylint: disable=unused-import
    FetcherConstructorType, fetch_document, jobloaderctx,
    load_overrides, make_tool, resolve_overrides, resolve_tool_uri,
    validate_document)
from .loghandler import _logger, defaultStreamHandler
from .mutation import MutationManager
from .pack import pack
from .pathmapper import (adjustDirObjs, normalizeFilesDirs, trim_listing,
                         visit_class)
from .process import (Process, scandeps,   # pylint: disable=unused-import
                      shortname, use_custom_schema, use_standard_schema)
from .resolver import ga4gh_tool_registries, tool_resolver
from .secrets import SecretStore
from .software_requirements import (DependenciesConfiguration,
                                    get_container_from_software_requirements)
from .stdfsaccess import StdFsAccess
from .update import ALLUPDATES, UPDATES
from .utils import (DEFAULT_TMP_PREFIX, add_sizes, json_dumps, onWindows,
                    windows_default_container_id)
from .context import LoadingContext, RuntimeContext, getdefault
from .builder import HasReqsHints

def generate_example_input(inptype):
    # type: (Union[Text, Dict[Text, Any]]) -> Any
    defaults = {u'null': 'null',
                u'Any': 'null',
                u'boolean': False,
                u'int': 0,
                u'long': 0,
                u'float': 0.1,
                u'double': 0.1,
                u'string': 'default_string',
                u'File': {'class': 'File',
                          'path': 'default/file/path'},
                u'Directory': {'class': 'Directory',
                               'path': 'default/directory/path'}
               }  # type: Dict[Text, Any]
    if (not isinstance(inptype, string_types) and
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
            return [generate_example_input(inptype['items'])]
        elif inptype['type'] == 'enum':
            return 'valid_enum_value'
            # TODO: list valid values in a comment
        elif inptype['type'] == 'record':
            record = {}
            for field in inptype['fields']:
                record[shortname(field['name'])] = generate_example_input(
                    field['type'])
            return record
    elif isinstance(inptype, string_types):
        return defaults.get(Text(inptype), 'custom_type')
        # TODO: support custom types, complex arrays


def generate_input_template(tool):
    # type: (Process) -> Dict[Text, Any]
    template = {}
    for inp in tool.tool["inputs"]:
        name = shortname(inp["id"])
        inptype = inp["type"]
        template[name] = generate_example_input(inptype)
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
                   t,                       # type: Process
                   loader,                  # type: Loader
                   stdout,                  # type: Union[TextIO, StreamWriter]
                   print_input_deps=False,  # type: bool
                   relative_deps=False,     # type: bool
                   make_fs_access=None,     # type: Callable[[Text], StdFsAccess]
                   input_basedir="",        # type: Text
                   secret_store=None        # type: SecretStore
                  ):  # type: (...) -> Union[MutableMapping[Text, Any], int]

    secrets_req, _ = t.get_requirement("http://commonwl.org/cwltool#Secrets")
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
                    job_order_object = cast(
                        MutableMapping, loader.resolve_ref(cmd_line["job_order"])[0])
                except Exception as e:
                    _logger.error(Text(e), exc_info=args.debug)
                    return 1
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

    for inp in t.tool["inputs"]:
        if "default" in inp and (
                not job_order_object or shortname(inp["id"]) not in job_order_object):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

    if not job_order_object:
        if len(t.tool["inputs"]) > 0:
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

    def pathToLoc(p):
        if "location" not in p and "path" in p:
            p["location"] = p["path"]
            del p["path"]

    ns = {}  # type: Dict[Text, Union[Dict[Any, Any], Text, Iterable[Text]]]
    ns.update(t.metadata.get("$namespaces", {}))
    ld = Loader(ns)

    def expand_formats(p):
        if "format" in p:
            p["format"] = ld.expand_url(p["format"], "")

    visit_class(job_order_object, ("File", "Directory"), pathToLoc)
    visit_class(job_order_object, ("File",), add_sizes)
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
              basedir=None      # type: Text
             ):  # type: (...) -> None
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

        visit_class(deps, ("File", "Directory"), functools.partial(make_relative, base))

    stdout.write(json_dumps(deps, indent=4))


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


def versionstring():  # type: () -> Text
    pkg = pkg_resources.require("cwltool")
    if pkg:
        return u"%s %s" % (sys.argv[0], pkg[0].version)
    return u"%s %s" % (sys.argv[0], "unknown version")

def supportedCWLversions(enable_dev):  # type: (bool) -> List[Text]
    # ALLUPDATES and UPDATES are dicts
    if enable_dev:
        versions = list(ALLUPDATES)
    else:
        versions = list(UPDATES)
    versions.sort()
    return versions

def main(argsl=None,                  # type: List[str]
         args=None,                   # type: argparse.Namespace
         job_order_object=None,       # type: MutableMapping[Text, Any]
         stdin=sys.stdin,             # type: IO[Any]
         stdout=None,                 # type: Union[TextIO, codecs.StreamWriter]
         stderr=sys.stderr,           # type: IO[Any]
         versionfunc=versionstring,   # type: Callable[[], Text]
         logger_handler=None,         #
         custom_schema_callback=None, # type: Callable[[], None]
         executor=None,               # type: Callable[..., Tuple[Dict[Text, Any], Text]]
         loadingContext=None,         # type: LoadingContext
         runtimeContext=None          # type: RuntimeContext
        ):  # type: (...) -> int
    if not stdout:  # force UTF-8 even if the console is configured differently
        if (hasattr(sys.stdout, "encoding")  # type: ignore
                and sys.stdout.encoding != 'UTF-8'):  # type: ignore
            if six.PY3 and hasattr(sys.stdout, "detach"):
                stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            else:
                stdout = codecs.getwriter('utf-8')(sys.stdout)  # type: ignore
        else:
            stdout = cast(TextIO, sys.stdout)  # type: ignore

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
        for key, val in six.iteritems(get_default_args()):
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

        if loadingContext is None:
            loadingContext = LoadingContext(vars(args))
        else:
            loadingContext = loadingContext.copy()

        loadingContext.disable_js_validation = \
                args.disable_js_validation or (not args.do_validate)
        loadingContext.construct_tool_object = getdefault(loadingContext.construct_tool_object, workflow.default_make_tool)
        loadingContext.resolver = getdefault(loadingContext.resolver, tool_resolver)

        uri, tool_file_uri = resolve_tool_uri(args.workflow,
                                              resolver=loadingContext.resolver,
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

            if args.print_pre:
                stdout.write(json_dumps(processobj, indent=4))
                return 0

            loadingContext.overrides_list.extend(metadata.get("cwltool:overrides", []))

            tool = make_tool(document_loader, avsc_names,
                             metadata, uri, loadingContext)
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

        initialized_job_order_object = 255  # type: Union[MutableMapping[Text, Any], int]
        try:
            initialized_job_order_object = init_job_order(job_order_object, args, tool,
                                               jobloader, stdout,
                                               print_input_deps=args.print_input_deps,
                                               relative_deps=args.relative_deps,
                                               input_basedir=input_basedir,
                                               secret_store=runtimeContext.secret_store)
        except SystemExit as err:
            return err.code

        if not executor:
            if args.parallel:
                executor = MultithreadedJobExecutor()
            else:
                executor = SingleJobExecutor()
        assert executor is not None

        if isinstance(initialized_job_order_object, int):
            return initialized_job_order_object

        try:
            runtimeContext.basedir = input_basedir
            del args.workflow
            del args.job_order

            conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)  # Text
            use_conda_dependencies = getattr(args, "beta_conda_dependencies", None)  # Text

            job_script_provider = None  # type: Optional[DependenciesConfiguration]
            if conf_file or use_conda_dependencies:
                runtimeContext.job_script_provider = DependenciesConfiguration(args)

            runtimeContext.find_default_container = \
                    functools.partial(find_default_container, args)
            runtimeContext.make_fs_access = getdefault(runtimeContext.make_fs_access, StdFsAccess)

            (out, status) = executor(tool,
                                     initialized_job_order_object,
                                     runtimeContext,
                                     logger=_logger)

            # This is the workflow output, it needs to be written
            if out is not None:

                def loc_to_path(obj):
                    for field in ("path", "nameext", "nameroot", "dirname"):
                        if field in obj:
                            del obj[field]
                    if obj["location"].startswith("file://"):
                        obj["path"] = uri_file_path(obj["location"])

                visit_class(out, ("File", "Directory"), loc_to_path)

                # Unsetting the Generation fron final output object
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
                u"Workflow error%s:\n%s", try_again_msg, strip_dup_lineno(six.text_type(exc)),
                exc_info=args.debug)
            return 1
        except Exception as exc:
            _logger.error(
                u"Unhandled error%s:\n  %s", try_again_msg, exc, exc_info=args.debug)
            return 1

    finally:
        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


def find_default_container(args, builder):
    # type: (argparse.Namespace, HasReqsHints) -> Optional[Text]
    default_container = None
    if args.default_container:
        default_container = args.default_container
    elif args.beta_use_biocontainers:
        default_container = get_container_from_software_requirements(args, builder)

    return default_container


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
