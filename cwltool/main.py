#!/usr/bin/env python

import argparse
import json
import os
import sys
import logging
import copy
import tempfile
import ruamel.yaml as yaml
import urlparse
import hashlib
import pkg_resources  # part of setuptools
import functools

import rdflib
import requests
from typing import (Union, Any, AnyStr, cast, Callable, Dict, Sequence, Text,
    Tuple, Type, IO)

from schema_salad.ref_resolver import Loader, Fetcher
import schema_salad.validate as validate
import schema_salad.jsonld_context
import schema_salad.makedoc
from schema_salad.sourceline import strip_dup_lineno

from . import workflow
from .errors import WorkflowException, UnsupportedRequirement
from .cwlrdf import printrdf, printdot
from .process import shortname, Process, getListing, relocateOutputs, cleanIntermediate, scandeps, normalizeFilesDirs
from .load_tool import fetch_document, validate_document, make_tool
from . import draft2tool
from .resolver import tool_resolver
from .builder import adjustFileObjs, adjustDirObjs
from .stdfsaccess import StdFsAccess
from .pack import pack

_logger = logging.getLogger("cwltool")

defaultStreamHandler = logging.StreamHandler()
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)


def arg_parser():  # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(description='Reference executor for Common Workflow Language')
    parser.add_argument("--basedir", type=Text)
    parser.add_argument("--outdir", type=Text, default=os.path.abspath('.'),
                        help="Output directory, default current directory")

    parser.add_argument("--no-container", action="store_false", default=True,
                        help="Do not execute jobs in a Docker container, even when specified by the CommandLineTool",
                        dest="use_container")

    parser.add_argument("--preserve-environment", type=Text, action="append",
                        help="Preserve specific environment variable when running CommandLineTools.  May be provided multiple times.",
                        metavar="ENVVAR",
                        default=["PATH"],
                        dest="preserve_environment")

    parser.add_argument("--preserve-entire-environment", action="store_true",
                        help="Preserve entire parent environment when running CommandLineTools.",
                        default=False,
                        dest="preserve_entire_environment")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--rm-container", action="store_true", default=True,
                        help="Delete Docker container used by jobs after they exit (default)",
                        dest="rm_container")

    exgroup.add_argument("--leave-container", action="store_false",
                        default=True, help="Do not delete Docker container used by jobs after they exit",
                        dest="rm_container")

    parser.add_argument("--tmpdir-prefix", type=Text,
                        help="Path prefix for temporary directories",
                        default="tmp")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--tmp-outdir-prefix", type=Text,
                        help="Path prefix for intermediate output directories",
                        default="tmp")

    exgroup.add_argument("--cachedir", type=Text, default="",
                        help="Directory to cache intermediate workflow outputs to avoid recomputing steps.")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--rm-tmpdir", action="store_true", default=True,
                        help="Delete intermediate temporary directories (default)",
                        dest="rm_tmpdir")

    exgroup.add_argument("--leave-tmpdir", action="store_false",
                        default=True, help="Do not delete intermediate temporary directories",
                        dest="rm_tmpdir")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--move-outputs", action="store_const", const="move", default="move",
                        help="Move output files to the workflow output directory and delete intermediate output directories (default).",
                        dest="move_outputs")

    exgroup.add_argument("--leave-outputs", action="store_const", const="leave", default="move",
                        help="Leave output files in intermediate output directories.",
                        dest="move_outputs")

    exgroup.add_argument("--copy-outputs", action="store_const", const="copy", default="move",
                         help="Copy output files to the workflow output directory, don't delete intermediate output directories.",
                         dest="move_outputs")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--enable-pull", default=True, action="store_true",
                        help="Try to pull Docker images", dest="enable_pull")

    exgroup.add_argument("--disable-pull", default=True, action="store_false",
                        help="Do not try to pull Docker images", dest="enable_pull")

    parser.add_argument("--rdf-serializer",
                        help="Output RDF serialization format used by --print-rdf (one of turtle (default), n3, nt, xml)",
                        default="turtle")

    parser.add_argument("--eval-timeout",
                        help="Time to wait for a Javascript expression to evaluate before giving an error, default 20s.",
                        type=float,
                        default=20)

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--print-rdf", action="store_true",
                        help="Print corresponding RDF graph for workflow and exit")
    exgroup.add_argument("--print-dot", action="store_true", help="Print workflow visualization in graphviz format and exit")
    exgroup.add_argument("--print-pre", action="store_true", help="Print CWL document after preprocessing.")
    exgroup.add_argument("--print-deps", action="store_true", help="Print CWL document dependencies.")
    exgroup.add_argument("--print-input-deps", action="store_true", help="Print input object document dependencies.")
    exgroup.add_argument("--pack", action="store_true", help="Combine components into single document and print.")
    exgroup.add_argument("--version", action="store_true", help="Print version and exit")
    exgroup.add_argument("--validate", action="store_true", help="Validate CWL document only.")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--strict", action="store_true", help="Strict validation (unrecognized or out of place fields are error)",
                         default=True, dest="strict")
    exgroup.add_argument("--non-strict", action="store_false", help="Lenient validation (ignore unrecognized fields)",
                         default=True, dest="strict")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--verbose", action="store_true", help="Default logging")
    exgroup.add_argument("--quiet", action="store_true", help="Only print warnings and errors.")
    exgroup.add_argument("--debug", action="store_true", help="Print even more logging")

    parser.add_argument("--tool-help", action="store_true", help="Print command line help for tool")

    parser.add_argument("--relative-deps", choices=['primary', 'cwd'],
        default="primary", help="When using --print-deps, print paths "
        "relative to primary file or current working directory.")

    parser.add_argument("--enable-dev", action="store_true",
                        help="Allow loading and running development versions "
                        "of CWL spec.", default=False)

    parser.add_argument("--default-container",
                        help="Specify a default docker container that will be used if the workflow fails to specify one.")
    parser.add_argument("--no-match-user", action="store_true",
                        help="Disable passing the current uid to 'docker run --user`")
    parser.add_argument("--disable-net", action="store_true",
                        help="Use docker's default networking for containers;"
                        " the default is to enable networking.")
    parser.add_argument("--custom-net", type=Text,
                        help="Will be passed to `docker run` as the '--net' "
                        "parameter. Implies '--enable-net'.")

    parser.add_argument("--on-error", type=Text,
                        help="Desired workflow behavior when a step fails.  One of 'stop' or 'continue'. "
                        "Default is 'stop.", default="stop")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--compute-checksum", action="store_true", default=True,
                        help="Compute checksum of contents while collecting outputs",
                        dest="compute_checksum")
    exgroup.add_argument("--no-compute-checksum", action="store_false",
                        help="Do not compute checksum of contents while collecting outputs",
                        dest="compute_checksum")

    parser.add_argument("--relax-path-checks", action="store_true",
            default=False, help="Relax requirements on path names. Currently "
            "allows spaces.", dest="relax_path_checks")
    parser.add_argument("workflow", type=Text, nargs="?", default=None)
    parser.add_argument("job_order", nargs=argparse.REMAINDER)

    return parser


def single_job_executor(t, job_order_object, **kwargs):
    # type: (Process, Dict[Text, Any], **Any) -> Union[Text, Dict[Text, Text]]
    final_output = []
    final_status = []

    def output_callback(out, processStatus):
        final_status.append(processStatus)
        if processStatus == "success":
            _logger.info(u"Final process status is %s", processStatus)
        else:
            _logger.warn(u"Final process status is %s", processStatus)
        final_output.append(out)

    if "basedir" not in kwargs:
        raise WorkflowException("Must provide 'basedir' in kwargs")

    output_dirs = set()
    finaloutdir = kwargs.get("outdir")
    kwargs["outdir"] = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"]) if kwargs.get("tmp_outdir_prefix") else tempfile.mkdtemp()
    output_dirs.add(kwargs["outdir"])

    jobReqs = None
    if "cwl:requirements" in job_order_object:
        jobReqs = job_order_object["cwl:requirements"]
    elif ("cwl:defaults" in t.metadata and "cwl:requirements" in
            t.metadata["cwl:defaults"]):
        jobReqs = t.metadata["cwl:defaults"]["cwl:requirements"]
    if jobReqs:
        for req in jobReqs:
            t.requirements.append(req)

    jobiter = t.job(job_order_object,
                    output_callback,
                    **kwargs)

    try:
        for r in jobiter:
            if r.outdir:
                output_dirs.add(r.outdir)

            if r:
                r.run(**kwargs)
            else:
                raise WorkflowException("Workflow cannot make any more progress.")
    except WorkflowException:
        raise
    except Exception as e:
        _logger.exception("Got workflow error")
        raise WorkflowException(Text(e))

    if final_status[0] != "success":
        raise WorkflowException(u"Process status is %s" % (final_status))

    if final_output[0] and finaloutdir:
        final_output[0] = relocateOutputs(final_output[0], finaloutdir,
                                          output_dirs, kwargs.get("move_outputs"))

    if kwargs.get("rm_tmpdir"):
        cleanIntermediate(output_dirs)

    return final_output[0]

class FSAction(argparse.Action):
    objclass = None  # type: Text

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # type: (List[Text], Text, Any, **Any) -> None
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FSAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # type: (argparse.ArgumentParser, argparse.Namespace, Union[AnyStr, Sequence[Any], None], AnyStr) -> None
        setattr(namespace,
            self.dest,  # type: ignore
            {"class": self.objclass,
             "location": "file://%s" % os.path.abspath(cast(AnyStr, values))})

class FSAppendAction(argparse.Action):
    objclass = None  # type: Text

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # type: (List[Text], Text, Any, **Any) -> None
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FSAppendAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # type: (argparse.ArgumentParser, argparse.Namespace, Union[AnyStr, Sequence[Any], None], AnyStr) -> None
        g = getattr(namespace,
                    self.dest  # type: ignore
                    )
        if not g:
            g = []
            setattr(namespace,
                    self.dest,  # type: ignore
                    g)
        g.append(
            {"class": self.objclass,
             "location": "file://%s" % os.path.abspath(cast(AnyStr, values))})

class FileAction(FSAction):
    objclass = "File"

class DirectoryAction(FSAction):
    objclass = "Directory"

class FileAppendAction(FSAppendAction):
    objclass = "File"

class DirectoryAppendAction(FSAppendAction):
    objclass = "Directory"


def add_argument(toolparser, name, inptype, records, description="",
        default=None):
    # type: (argparse.ArgumentParser, Text, Any, List[Text], Text, Any) -> None
        if len(name) == 1:
            flag = "-"
        else:
            flag = "--"

        required = True
        if isinstance(inptype, list):
            if inptype[0] == "null":
                required = False
                if len(inptype) == 2:
                    inptype = inptype[1]
                else:
                    _logger.debug(u"Can't make command line argument from %s", inptype)
                    return None

        ahelp = description.replace("%", "%%")
        action = None  # type: Union[argparse.Action, Text]
        atype = None  # type: Any

        if inptype == "File":
            action = cast(argparse.Action, FileAction)
        elif inptype == "Directory":
            action = cast(argparse.Action, DirectoryAction)
        elif isinstance(inptype, dict) and inptype["type"] == "array":
            if inptype["items"] == "File":
                action = cast(argparse.Action, FileAppendAction)
            elif inptype["items"] == "Directory":
                action = cast(argparse.Action, DirectoryAppendAction)
            else:
                action = "append"
        elif isinstance(inptype, dict) and inptype["type"] == "enum":
            atype = Text
        elif isinstance(inptype, dict) and inptype["type"] == "record":
            records.append(name)
            for field in inptype['fields']:
                fieldname = name+"."+shortname(field['name'])
                fieldtype = field['type']
                fielddescription = field.get("doc", "")
                add_argument(
                    toolparser, fieldname, fieldtype, records,
                    fielddescription)
            return
        if inptype == "string":
            atype = Text
        elif inptype == "int":
            atype = int
        elif inptype == "double":
            atype = float
        elif inptype == "float":
            atype = float
        elif inptype == "boolean":
            action = "store_true"

        if default:
            required = False

        if not atype and not action:
            _logger.debug(u"Can't make command line argument from %s", inptype)
            return None

        if inptype != "boolean":
            typekw = { 'type': atype }
        else:
            typekw = {}

        toolparser.add_argument(  # type: ignore
            flag + name, required=required, help=ahelp, action=action,
            default=default, **typekw)


def generate_parser(toolparser, tool, namemap, records):
    # type: (argparse.ArgumentParser, Process, Dict[Text, Text], List[Text]) -> argparse.ArgumentParser
    toolparser.add_argument("job_order", nargs="?", help="Job input json file")
    namemap["job_order"] = "job_order"

    for inp in tool.tool["inputs"]:
        name = shortname(inp["id"])
        namemap[name.replace("-", "_")] = name
        inptype = inp["type"]
        description = inp.get("doc", "")
        default = inp.get("default", None)
        add_argument(toolparser, name, inptype, records, description, default)

    return toolparser


def load_job_order(args, t, stdin, print_input_deps=False, relative_deps=False,
                   stdout=sys.stdout, make_fs_access=None, fetcher_constructor=None):
    # type: (argparse.Namespace, Process, IO[Any], bool, bool, IO[Any], Callable[[Text], StdFsAccess], Callable[[Dict[unicode, unicode], requests.sessions.Session], Fetcher]) -> Union[int, Tuple[Dict[Text, Any], Text]]

    job_order_object = None

    jobloaderctx = {
        u"path": {u"@type": u"@id"},
        u"location": {u"@type": u"@id"},
        u"format": {u"@type": u"@id"},
        u"id": u"@id"}
    jobloaderctx.update(t.metadata.get("$namespaces", {}))
    loader = Loader(jobloaderctx, fetcher_constructor=fetcher_constructor)

    if len(args.job_order) == 1 and args.job_order[0][0] != "-":
        job_order_file = args.job_order[0]
    elif len(args.job_order) == 1 and args.job_order[0] == "-":
        job_order_object = yaml.load(stdin)
        job_order_object, _ = loader.resolve_all(job_order_object, "")
    else:
        job_order_file = None

    if job_order_object:
        input_basedir = args.basedir if args.basedir else os.getcwd()
    elif job_order_file:
        input_basedir = args.basedir if args.basedir else os.path.abspath(os.path.dirname(job_order_file))
        try:
            job_order_object, _ = loader.resolve_ref(job_order_file, checklinks=False)
        except Exception as e:
            _logger.error(Text(e), exc_info=args.debug)
            return 1
        toolparser = None
    else:
        input_basedir = args.basedir if args.basedir else os.getcwd()
        namemap = {}  # type: Dict[Text, Text]
        records = []  # type: List[Text]
        toolparser = generate_parser(
            argparse.ArgumentParser(prog=args.workflow), t, namemap, records)
        if toolparser:
            if args.tool_help:
                toolparser.print_help()
                return 0
            cmd_line = vars(toolparser.parse_args(args.job_order))
            for record_name in records:
                record = {}
                record_items = {
                    k:v for k,v in cmd_line.iteritems()
                    if k.startswith(record_name)}
                for key, value in record_items.iteritems():
                    record[key[len(record_name)+1:]] = value
                    del cmd_line[key]
                cmd_line[str(record_name)] = record

            if cmd_line["job_order"]:
                try:
                    input_basedir = args.basedir if args.basedir else os.path.abspath(os.path.dirname(cmd_line["job_order"]))
                    job_order_object = loader.resolve_ref(cmd_line["job_order"])
                except Exception as e:
                    _logger.error(Text(e), exc_info=args.debug)
                    return 1
            else:
                job_order_object = {"id": args.workflow}

            job_order_object.update({namemap[k]: v for k,v in cmd_line.items()})

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
            print u"\nOptions for %s " % args.workflow
            toolparser.print_help()
        _logger.error("")
        _logger.error("Input object required, use --help for details")
        return 1

    if print_input_deps:
        printdeps(job_order_object, loader, stdout, relative_deps, "",
                  basedir=u"file://%s/" % input_basedir)
        return 0

    def pathToLoc(p):
        if "location" not in p and "path" in p:
            p["location"] = p["path"]
            del p["path"]

    adjustDirObjs(job_order_object, pathToLoc)
    adjustFileObjs(job_order_object, pathToLoc)
    normalizeFilesDirs(job_order_object)
    adjustDirObjs(job_order_object, cast(Callable[..., Any],
        functools.partial(getListing, make_fs_access(input_basedir))))

    if "cwl:tool" in job_order_object:
        del job_order_object["cwl:tool"]
    if "id" in job_order_object:
        del job_order_object["id"]

    return (job_order_object, input_basedir)

def makeRelative(base, ob):
    u = ob.get("location", ob.get("path"))
    if ":" in u.split("/")[0] and not u.startswith("file://"):
        pass
    else:
        if u.startswith("file://"):
            u = u[7:]
        ob["location"] = os.path.relpath(u, base)

def printdeps(obj, document_loader, stdout, relative_deps, uri, basedir=None):
    # type: (Dict[Text, Any], Loader, IO[Any], bool, Text, Text) -> None
    deps = {"class": "File",
            "location": uri}  # type: Dict[Text, Any]

    def loadref(b, u):
        return document_loader.fetch(document_loader.fetcher.urljoin(b, u))

    sf = scandeps(
        basedir if basedir else uri, obj, set(("$import", "run")),
        set(("$include", "$schemas", "location")), loadref)
    if sf:
        deps["secondaryFiles"] = sf

    if relative_deps:
        if relative_deps == "primary":
            base = basedir if basedir else os.path.dirname(uri)
        elif relative_deps == "cwd":
            base = "file://" + os.getcwd()
        else:
            raise Exception(u"Unknown relative_deps %s" % relative_deps)

        adjustFileObjs(deps, functools.partial(makeRelative, base))
        adjustDirObjs(deps, functools.partial(makeRelative, base))

    stdout.write(json.dumps(deps, indent=4))

def print_pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[unicode, Any], List[Dict[unicode, Any]]], unicode, Dict[unicode, Any]) -> str
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


def main(argsl=None,  # type: List[str]
         args=None,   # type: argparse.Namespace
         executor=single_job_executor,  # type: Callable[..., Union[Text, Dict[Text, Text]]]
         makeTool=workflow.defaultMakeTool,  # type: Callable[..., Process]
         selectResources=None,  # type: Callable[[Dict[Text, int]], Dict[Text, int]]
         stdin=sys.stdin,  # type: IO[Any]
         stdout=sys.stdout,  # type: IO[Any]
         stderr=sys.stderr,  # type: IO[Any]
         versionfunc=versionstring,  # type: Callable[[], Text]
         job_order_object=None,  # type: Union[Tuple[Dict[Text, Any], Text], int]
         make_fs_access=StdFsAccess,  # type: Callable[[Text], StdFsAccess]
         fetcher_constructor=None,  # type: Callable[[Dict[unicode, unicode], requests.sessions.Session], Fetcher]
         resolver=tool_resolver,
         logger_handler=None
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

        # If caller provided custom arguments, it may be not every expected
        # option is set, so fill in no-op defaults to avoid crashing when
        # dereferencing them in args.
        for k,v in {'print_deps': False,
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
                    'version': False,
                    'enable_dev': False,
                    'strict': True,
                    'rdf_serializer': None,
                    'basedir': None,
                    'tool_help': False,
                    'workflow': None,
                    'job_order': None,
                    'pack': False,
                    'on_error': 'continue',
                    'relax_path_checks': False,
                    'validate': False}.iteritems():
            if not hasattr(args, k):
                setattr(args, k, v)

        if args.quiet:
            _logger.setLevel(logging.WARN)
        if args.debug:
            _logger.setLevel(logging.DEBUG)

        if args.version:
            print versionfunc()
            return 0
        else:
            _logger.info(versionfunc())

        if not args.workflow:
            if os.path.isfile("CWLFile"):
                setattr(args, "workflow", "CWLFile")
            else:
                _logger.error("")
                _logger.error("CWL document required, try --help for details")
                return 1
        if args.relax_path_checks:
            draft2tool.ACCEPTLIST_RE = draft2tool.ACCEPTLIST_EN_RELAXED_RE

        try:
            document_loader, workflowobj, uri = fetch_document(args.workflow, resolver=resolver, fetcher_constructor=fetcher_constructor)

            if args.print_deps:
                printdeps(workflowobj, document_loader, stdout, args.relative_deps, uri)
                return 0

            document_loader, avsc_names, processobj, metadata, uri \
                = validate_document(document_loader, workflowobj, uri,
                                    enable_dev=args.enable_dev, strict=args.strict,
                                    preprocess_only=args.print_pre or args.pack,
                                    fetcher_constructor=fetcher_constructor)

            if args.validate:
                return 0

            if args.pack:
                stdout.write(print_pack(document_loader, processobj, uri, metadata))
                return 0

            if args.print_pre:
                stdout.write(json.dumps(processobj, indent=4))
                return 0

            tool = make_tool(document_loader, avsc_names, metadata, uri,
                    makeTool, vars(args))

            if args.print_rdf:
                printrdf(tool, document_loader.ctx, args.rdf_serializer, stdout)
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

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if getattr(args, dirprefix) and getattr(args, dirprefix) != 'tmp':
                sl = "/" if getattr(args, dirprefix).endswith("/") or dirprefix == "cachedir" else ""
                setattr(args, dirprefix,
                        os.path.abspath(getattr(args, dirprefix))+sl)
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

        if job_order_object is None:
            job_order_object = load_job_order(args, tool, stdin,
                                              print_input_deps=args.print_input_deps,
                                              relative_deps=args.relative_deps,
                                              stdout=stdout,
                                              make_fs_access=make_fs_access,
                                              fetcher_constructor=fetcher_constructor)

        if isinstance(job_order_object, int):
            return job_order_object

        try:
            setattr(args, 'basedir', job_order_object[1])
            del args.workflow
            del args.job_order
            out = executor(tool, job_order_object[0],
                           makeTool=makeTool,
                           select_resources=selectResources,
                           make_fs_access=make_fs_access,
                           **vars(args))

            # This is the workflow output, it needs to be written
            if out is not None:
                def locToPath(p):
                    if p["location"].startswith("file://"):
                        p["path"] = p["location"][7:]

                adjustDirObjs(out, locToPath)
                adjustFileObjs(out, locToPath)

                if isinstance(out, basestring):
                    stdout.write(out)
                else:
                    stdout.write(json.dumps(out, indent=4))
                stdout.write("\n")
                stdout.flush()
            else:
                return 1
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
                "information:\n%s", strip_dup_lineno(unicode(exc)), exc_info=args.debug)
            return 1
        except Exception as exc:
            _logger.error(
                u"Unhandled error, try again with --debug for more information:\n"
                "  %s", exc, exc_info=args.debug)
            return 1

        return 0
    finally:
        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
