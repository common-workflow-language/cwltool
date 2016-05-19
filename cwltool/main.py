#!/usr/bin/env python

from . import draft2tool
import argparse
from schema_salad.ref_resolver import Loader
import string
import json
import os
import sys
import logging
from . import workflow
from .errors import WorkflowException
from . import process
from .cwlrdf import printrdf, printdot
from .process import shortname, Process
from .load_tool import fetch_document, validate_document, make_tool
import schema_salad.validate as validate
import tempfile
import schema_salad.jsonld_context
import schema_salad.makedoc
import yaml
import urlparse
import pkg_resources  # part of setuptools
import rdflib
import hashlib
from typing import Union, Any, cast, Callable, Dict, Tuple, IO

_logger = logging.getLogger("cwltool")

defaultStreamHandler = logging.StreamHandler()
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)


def arg_parser():  # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(description='Reference executor for Common Workflow Language')
    parser.add_argument("--conformance-test", action="store_true")
    parser.add_argument("--basedir", type=str)
    parser.add_argument("--outdir", type=str, default=os.path.abspath('.'),
                        help="Output directory, default current directory")

    parser.add_argument("--no-container", action="store_false", default=True,
                        help="Do not execute jobs in a Docker container, even when specified by the CommandLineTool",
                        dest="use_container")

    parser.add_argument("--preserve-environment", type=str, nargs='+',
                        help="Preserve specified environment variables when running CommandLineTools",
                        metavar=("VAR1,VAR2"),
                        default=("PATH",),
                        dest="preserve_environment")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--rm-container", action="store_true", default=True,
                        help="Delete Docker container used by jobs after they exit (default)",
                        dest="rm_container")

    exgroup.add_argument("--leave-container", action="store_false",
                        default=True, help="Do not delete Docker container used by jobs after they exit",
                        dest="rm_container")

    parser.add_argument("--tmpdir-prefix", type=str,
                        help="Path prefix for temporary directories",
                        default="tmp")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--tmp-outdir-prefix", type=str,
                        help="Path prefix for intermediate output directories",
                        default="tmp")

    exgroup.add_argument("--cachedir", type=str, default="",
                        help="Directory to cache intermediate workflow outputs to avoid recomputing steps.")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--rm-tmpdir", action="store_true", default=True,
                        help="Delete intermediate temporary directories (default)",
                        dest="rm_tmpdir")

    exgroup.add_argument("--leave-tmpdir", action="store_false",
                        default=True, help="Do not delete intermediate temporary directories",
                        dest="rm_tmpdir")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--move-outputs", action="store_true", default=True,
                        help="Move output files to the workflow output directory and delete intermediate output directories (default).",
                        dest="move_outputs")

    exgroup.add_argument("--leave-outputs", action="store_false", default=True,
                        help="Leave output files in intermediate output directories.",
                        dest="move_outputs")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--enable-pull", default=True, action="store_true",
                        help="Try to pull Docker images", dest="enable_pull")

    exgroup.add_argument("--disable-pull", default=True, action="store_false",
                        help="Do not try to pull Docker images", dest="enable_pull")

    parser.add_argument("--dry-run", action="store_true",
                        help="Load and validate but do not execute")

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
    exgroup.add_argument("--version", action="store_true", help="Print version and exit")

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

    parser.add_argument("--relative-deps", choices=['primary', 'cwd'], default="primary",
                         help="When using --print-deps, print paths relative to primary file or current working directory.")

    parser.add_argument("--enable-dev", action="store_true",
                        help="Allow loading and running development versions "
                        "of CWL spec.", default=False)

    parser.add_argument("--enable-net", action="store_true",
                        help="Use docker's default networking for containers;"
                        " the default is to disable networking.")
    parser.add_argument("--custom-net", type=str,
                        help="Will be passed to `docker run` as the '--net' "
                        "parameter. Implies '--enable-net'.")

    parser.add_argument("workflow", type=str, nargs="?", default=None)
    parser.add_argument("job_order", nargs=argparse.REMAINDER)

    return parser


def single_job_executor(t, job_order_object, **kwargs):
    # type: (Process, Dict[str,Any], str, argparse.Namespace,**Any) -> Union[str,Dict[str,str]]
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

    if kwargs.get("outdir"):
        pass
    elif kwargs.get("dry_run"):
        kwargs["outdir"] = "/tmp"
    else:
        kwargs["outdir"] = tempfile.mkdtemp()

    jobiter = t.job(job_order_object,
                    output_callback,
                    **kwargs)

    if kwargs.get("conformance_test"):
        job = jobiter.next()
        a = {"args": job.command_line}
        if job.stdin:
            a["stdin"] = job.pathmapper.mapper(job.stdin)[1]
        if job.stdout:
            a["stdout"] = job.stdout
        if job.generatefiles:
            a["createfiles"] = job.generatefiles
        return a
    else:
        try:
            for r in jobiter:
                if r:
                    r.run(**kwargs)
                else:
                    raise WorkflowException("Workflow cannot make any more progress.")
        except WorkflowException:
            raise
        except Exception as e:
            _logger.exception("Got workflow error")
            raise WorkflowException(unicode(e))

        if final_status[0] != "success":
            raise WorkflowException(u"Process status is %s" % (final_status))

        return final_output[0]


class FileAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # type: (List[str], str, Any, **Any) -> None
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FileAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # type: (argparse.ArgumentParser, argparse.Namespace, str, Any) -> None
        setattr(namespace, self.dest, {"class": "File", "path": values})


class FileAppendAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # type: (List[str], str, Any, **Any) -> None
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FileAppendAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # type: (argparse.ArgumentParser, argparse.Namespace, str, Any) -> None
        g = getattr(namespace, self.dest)
        if not g:
            g = []
            setattr(namespace, self.dest, g)
        g.append({"class": "File", "path": values})


def generate_parser(toolparser, tool, namemap):
    # type: (argparse.ArgumentParser, Process,Dict[str,str]) -> argparse.ArgumentParser
    toolparser.add_argument("job_order", nargs="?", help="Job input json file")
    namemap["job_order"] = "job_order"

    for inp in tool.tool["inputs"]:
        name = shortname(inp["id"])
        if len(name) == 1:
            flag = "-"
        else:
            flag = "--"

        namemap[name.replace("-", "_")] = name

        inptype = inp["type"]

        required = True
        if isinstance(inptype, list):
            if inptype[0] == "null":
                required = False
                if len(inptype) == 2:
                    inptype = inptype[1]
                else:
                    _logger.debug(u"Can't make command line argument from %s", inptype)
                    return None

        ahelp = inp.get("description", "").replace("%", "%%")
        action = None  # type: Union[argparse.Action,str]
        atype = None # type: Any
        default = None # type: Any

        if inptype == "File":
            action = cast(argparse.Action, FileAction)
        elif isinstance(inptype, dict) and inptype["type"] == "array":
            if inptype["items"] == "File":
                action = cast(argparse.Action, FileAppendAction)
            else:
                action = "append"

        if inptype == "string":
            atype = str
        elif inptype == "int":
            atype = int
        elif inptype == "float":
            atype = float
        elif inptype == "boolean":
            action = "store_true"

        if "default" in inp:
            default = inp["default"]
            required = False

        if not atype and not action:
            _logger.debug(u"Can't make command line argument from %s", inptype)
            return None

        if inptype != "boolean":
            typekw = { 'type': atype }
        else:
            typekw = {}

        toolparser.add_argument(flag + name, required=required,
                help=ahelp, action=action, default=default, **typekw)

    return toolparser


def load_job_order(args, t, stdin, print_input_deps=False, relative_deps=False, stdout=sys.stdout):
    # type: (argparse.Namespace, Process, argparse.ArgumentParser, IO[Any], bool, bool, IO[Any]) -> Union[int,Tuple[Dict[str,Any],str]]

    job_order_object = None

    if args.conformance_test:
        loader = Loader({})
    else:
        jobloaderctx = {
                "path": {"@type": "@id"},
                "format": {"@type": "@id"},
                "id": "@id"}
        jobloaderctx.update(t.metadata.get("$namespaces", {}))
        loader = Loader(jobloaderctx)

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
            job_order_object, _ = loader.resolve_ref(job_order_file)
        except Exception as e:
            _logger.error(str(e), exc_info=(e if args.debug else False))
            return 1
        toolparser = None
    else:
        input_basedir = args.basedir if args.basedir else os.getcwd()
        namemap = {}  # type: Dict[str,str]
        toolparser = generate_parser(argparse.ArgumentParser(prog=args.workflow), t, namemap)
        if toolparser:
            if args.tool_help:
                toolparser.print_help()
                return 0
            cmd_line = vars(toolparser.parse_args(args.job_order))

            if cmd_line["job_order"]:
                try:
                    input_basedir = args.basedir if args.basedir else os.path.abspath(os.path.dirname(cmd_line["job_order"]))
                    job_order_object = loader.resolve_ref(cmd_line["job_order"])
                except Exception as e:
                    _logger.error(str(e), exc_info=(e if args.debug else False))
                    return 1
            else:
                job_order_object = {"id": args.workflow}

            job_order_object.update({namemap[k]: v for k,v in cmd_line.items()})

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
        printdeps(job_order_object, loader, stdout, relative_deps,
                  basedir=u"file://%s/" % input_basedir)
        return 0

    if "cwl:tool" in job_order_object:
        del job_order_object["cwl:tool"]
    if "id" in job_order_object:
        del job_order_object["id"]

    return (job_order_object, input_basedir)


def printdeps(obj, document_loader, stdout, relative_deps, basedir=None):
    # type: (Dict[unicode, Any], Loader, IO[Any], bool, str) -> None
    deps = {"class": "File",
            "path": obj.get("id", "#")}

    def loadref(b, u):
        return document_loader.resolve_ref(u, base_url=b)[0]

    sf = process.scandeps(basedir if basedir else obj["id"], obj,
                          set(("$import", "run")),
                          set(("$include", "$schemas", "path")), loadref)
    if sf:
        deps["secondaryFiles"] = sf

    if relative_deps:
        if relative_deps == "primary":
            base = basedir if basedir else os.path.dirname(obj["id"])
        elif relative_deps == "cwd":
            base = "file://" + os.getcwd()
        else:
            raise Exception(u"Unknown relative_deps %s" % relative_deps)
        def makeRelative(u):
            if ":" in u.split("/")[0] and not u.startswith("file://"):
                return u
            return os.path.relpath(u, base)
        process.adjustFiles(deps, makeRelative)

    stdout.write(json.dumps(deps, indent=4))

def versionstring():
    # type: () -> unicode
    pkg = pkg_resources.require("cwltool")
    if pkg:
        return u"%s %s" % (sys.argv[0], pkg[0].version)
    else:
        return u"%s %s" % (sys.argv[0], "unknown version")


def main(argsl=None,
         args=None,
         executor=single_job_executor,
         makeTool=workflow.defaultMakeTool,
         selectResources=None,
         stdin=sys.stdin,
         stdout=sys.stdout,
         stderr=sys.stderr,
         versionfunc=versionstring,
         job_order_object=None):
    # type: (List[str],Callable[...,Union[str,Dict[str,str]]],Callable[...,Process],Callable[[Dict[str,int]],Dict[str,int]],argparse.ArgumentParser,IO[Any],IO[Any],IO[Any],Callable[[],unicode]) -> int

    _logger.removeHandler(defaultStreamHandler)
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
                    'job_order': None}.iteritems():
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
            _logger.error("")
            _logger.error("CWL document required, try --help for details")
            return 1

        try:
            document_loader, workflowobj, uri = fetch_document(args.workflow)

            if args.print_deps:
                printdeps(workflowobj, document_loader, stdout, args.relative_deps)
                return 0

            document_loader, avsc_names, processobj, metadata, uri \
                = validate_document(document_loader, workflowobj, uri,
                                    enable_dev=args.enable_dev, strict=args.strict,
                                    preprocess_only=args.print_pre)

            if args.print_pre:
                stdout.write(json.dumps(processobj, indent=4))
                return 0

            if args.print_rdf:
                printrdf(uri, processobj, document_loader.ctx, args.rdf_serializer, stdout)
                return 0

            if args.print_dot:
                printdot(uri, processobj, document_loader.ctx, stdout)
                return 0

            tool = make_tool(document_loader, avsc_names, processobj, metadata,
                             uri, makeTool, {})
        except (validate.ValidationException) as exc:
            _logger.error(u"Tool definition failed validation:\n%s", exc,
                          exc_info=(exc if args.debug else False))
            return 1
        except (RuntimeError, WorkflowException) as exc:
            _logger.error(u"Tool definition failed initialization:\n%s", exc,
                          exc_info=(exc if args.debug else False))
            return 1
        except Exception as exc:
            _logger.error(
                u"I'm sorry, I couldn't load this CWL file%s",
                ", try again with --debug for more information.\nThe error was: "
                "%s" % exc if not args.debug else ".  The error was:",
                exc_info=(exc if args.debug else False))
            return 1

        if isinstance(tool, int):
            return tool

        if args.tmp_outdir_prefix != 'tmp':
            # Use user defined temp directory (if it exists)
            args.tmp_outdir_prefix = os.path.abspath(args.tmp_outdir_prefix)
            if not os.path.exists(args.tmp_outdir_prefix):
                _logger.error("Intermediate output directory prefix doesn't exist.")
                return 1

        if args.tmpdir_prefix != 'tmp':
            # Use user defined prefix (if the folder exists)
            args.tmpdir_prefix = os.path.abspath(args.tmpdir_prefix)
            if not os.path.exists(args.tmpdir_prefix):
                _logger.error("Temporary directory prefix doesn't exist.")
                return 1

        if job_order_object is None:
            job_order_object = load_job_order(args, tool, stdin,
                                              print_input_deps=args.print_input_deps,
                                              relative_deps=args.relative_deps,
                                              stdout=stdout)

        if isinstance(job_order_object, int):
            return job_order_object

        if args.cachedir:
            args.cachedir = os.path.abspath(args.cachedir)
            args.move_outputs = False

        try:
            args.tmp_outdir_prefix = args.cachedir if args.cachedir else args.tmp_outdir_prefix
            args.basedir = job_order_object[1]
            del args.workflow
            del args.job_order
            out = executor(tool, job_order_object[0],
                           makeTool=makeTool,
                           select_resources=selectResources,
                           **vars(args))
            # This is the workflow output, it needs to be written
            if out is not None:
                if isinstance(out, basestring):
                    stdout.write(out)
                else:
                    stdout.write(json.dumps(out, indent=4))
                stdout.write("\n")
                stdout.flush()
            else:
                return 1
        except (validate.ValidationException) as exc:
            _logger.error(
                u"Input object failed validation:\n%s", exc,
                exc_info=(exc if args.debug else False))
            return 1
        except WorkflowException as exc:
            _logger.error(
                u"Workflow error, try again with --debug for more "
                "information:\n  %s", exc, exc_info=(exc if args.debug else False))
            return 1
        except Exception as exc:
            _logger.error(
                u"Unhandled error, try again with --debug for more information:\n"
                "  %s", exc, exc_info=(exc if args.debug else False))
            return 1

        return 0
    finally:
        _logger.removeHandler(stderr_handler)
        _logger.addHandler(defaultStreamHandler)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
