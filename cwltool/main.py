#!/usr/bin/env python

import draft2tool
import argparse
from schema_salad.ref_resolver import Loader
import json
import os
import sys
import logging
import workflow
import schema_salad.validate as validate
import tempfile
import schema_salad.jsonld_context
import schema_salad.makedoc
import yaml
import urlparse
import process
import job
from cwlrdf import printrdf, printdot
import pkg_resources  # part of setuptools
import update
from process import shortname
import rdflib

_logger = logging.getLogger("cwltool")

defaultStreamHandler = logging.StreamHandler()
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)

def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conformance-test", action="store_true")
    parser.add_argument("--basedir", type=str)
    parser.add_argument("--outdir", type=str, default=os.path.abspath('.'),
                        help="Output directory, default current directory")

    parser.add_argument("--no-container", action="store_false", default=True,
                        help="Do not execute jobs in a Docker container, even when specified by the CommandLineTool",
                        dest="use_container")

    parser.add_argument("--preserve-environment", type=str, nargs='+',
                        help="Preserve specified environment variables when running CommandLineTools",
                        metavar=("VAR1","VAR2"),
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

    parser.add_argument("--tmp-outdir-prefix", type=str,
                        help="Path prefix for intermediate output directories",
                        default="tmp")

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

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--print-rdf", action="store_true",
                        help="Print corresponding RDF graph for workflow and exit")
    exgroup.add_argument("--print-dot", action="store_true", help="Print workflow visualization in graphviz format and exit")
    exgroup.add_argument("--print-pre", action="store_true", help="Print CWL document after preprocessing.")
    exgroup.add_argument("--version", action="store_true", help="Print version and exit")
    exgroup.add_argument("--update", action="store_true", help="Update to latest CWL version, print and exit")

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

    parser.add_argument("workflow", type=str, nargs="?", default=None)
    parser.add_argument("job_order", nargs=argparse.REMAINDER)

    return parser

def single_job_executor(t, job_order, input_basedir, args, **kwargs):
    final_output = []
    final_status = []

    def output_callback(out, processStatus):
        final_status.append(processStatus)
        if processStatus == "success":
            _logger.info("Final process status is %s", processStatus)
        else:
            _logger.warn("Final process status is %s", processStatus)
        final_output.append(out)

    if kwargs.get("outdir"):
        pass
    elif kwargs.get("dry_run"):
        kwargs["outdir"] = "/tmp"
    else:
        kwargs["outdir"] = tempfile.mkdtemp()

    jobiter = t.job(job_order,
                    input_basedir,
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
                    raise workflow.WorkflowException("Workflow cannot make any more progress.")
        except workflow.WorkflowException:
            raise
        except Exception as e:
            _logger.exception("Got workflow error")
            raise workflow.WorkflowException("%s" % e, )

        if final_status[0] != "success":
            raise workflow.WorkflowException("Process status is %s" % (final_status))

        return final_output[0]

class FileAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FileAction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, {"class": "File", "path": values})

class FileAppendAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FileAppendAction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        g = getattr(namespace, self.dest)
        if not g:
            g = []
            setattr(namespace, self.dest, g)
        g.append({"class": "File", "path": values})

def generate_parser(toolparser, tool, namemap):
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
                    _logger.debug("Can't make command line argument from %s", inptype)
                    return None

        help = inp.get("description", "").replace("%", "%%")
        kwargs = {}

        if inptype == "File":
            kwargs["action"] = FileAction
        elif isinstance(inptype, dict) and inptype["type"] == "array":
            if inptype["items"] == "File":
                kwargs["action"] = FileAppendAction
            else:
                kwargs["action"] = "append"

        if inptype == "string":
            kwargs["type"] = str
        elif inptype == "int":
            kwargs["type"] = int
        elif inptype == "float":
            kwargs["type"] = float
        elif inptype == "boolean":
            kwargs["action"] = "store_true"

        if "default" in inp:
            kwargs["default"] = inp["default"]
            required = False

        if "type" not in kwargs and "action" not in kwargs:
            _logger.debug("Can't make command line argument from %s", inptype)
            return None

        toolparser.add_argument(flag + name, required=required, help=help, **kwargs)

    return toolparser


def load_tool(argsworkflow, updateonly, strict, makeTool, debug,
              print_pre=False,
              print_rdf=False,
              print_dot=False,
              rdf_serializer=None):
    (document_loader, avsc_names, schema_metadata) = process.get_schema()

    if isinstance(avsc_names, Exception):
        raise avsc_names

    split = urlparse.urlsplit(argsworkflow)
    if split.scheme:
        uri = argsworkflow
    else:
        uri = "file://" + os.path.abspath(argsworkflow)
    fileuri, urifrag = urlparse.urldefrag(uri)
    workflowobj = document_loader.fetch(fileuri)
    if isinstance(workflowobj, list):
        workflowobj = {"cwlVersion": "https://w3id.org/cwl/cwl#draft-2",
                       "id": fileuri,
                       "@graph": workflowobj}

    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj = workflowobj
        workflowobj = document_loader.fetch(urlparse.urljoin(uri, workflowobj["cwl:tool"]))

    workflowobj = update.update(workflowobj, document_loader, fileuri)
    document_loader.idx.clear()

    if updateonly:
        print json.dumps(workflowobj, indent=4)
        return 0

    try:
        processobj, metadata = schema_salad.schema.load_and_validate(document_loader, avsc_names, workflowobj, strict)
    except (schema_salad.validate.ValidationException, RuntimeError) as e:
        _logger.error("Tool definition failed validation:\n%s", e, exc_info=(e if debug else False))
        return 1

    if print_pre:
        print json.dumps(processobj, indent=4)
        return 0

    if print_rdf:
        printrdf(argsworkflow, processobj, document_loader.ctx, rdf_serializer)
        return 0

    if print_dot:
        printdot(argsworkflow, processobj, document_loader.ctx, rdf_serializer)
        return 0

    if urifrag:
        processobj, _ = document_loader.resolve_ref(uri)
    elif isinstance(processobj, list):
        _logger.error("Tool file contains graph of multiple objects, must specify one of #%s",
                      ", #".join(urlparse.urldefrag(i["id"])[1]
                                 for i in processobj if "id" in i))
        return 1

    try:
        t = makeTool(processobj, strict=strict, makeTool=makeTool, loader=document_loader, avsc_names=avsc_names)
    except (schema_salad.validate.ValidationException) as e:
        _logger.error("Tool definition failed validation:\n%s", e, exc_info=(e if debug else False))
        return 1
    except (RuntimeError, workflow.WorkflowException) as e:
        _logger.error("Tool definition failed initialization:\n%s", e, exc_info=(e if debug else False))
        return 1

    if jobobj:
        for inp in t.tool["inputs"]:
            if shortname(inp["id"]) in jobobj:
                inp["default"] = jobobj[shortname(inp["id"])]

    if metadata:
        t.metadata = metadata
    else:
        t.metadata = {"$namespaces": t.tool.get("$namespaces", {}), "$schemas": t.tool.get("$schemas", [])}

    return t

def load_job_order(args, t, parser):

    job_order_object = None

    if args.conformance_test:
        loader = Loader({})
    else:
        jobloaderctx = {"path": {"@type": "@id"}, "format": {"@type": "@id"}}
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
            _logger.error(e, exc_info=(e if args.debug else False))
            return 1
        toolparser = None
    else:
        input_basedir = args.basedir if args.basedir else os.getcwd()
        namemap = {}
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
                    _logger.error(e, exc_info=(e if args.debug else False))
                    return 1
            else:
                job_order_object = {}

            job_order_object.update({namemap[k]: v for k,v in cmd_line.items()})

            _logger.debug("Parsed job order from command line: %s", job_order_object)
        else:
            job_order_object = None

    for inp in t.tool["inputs"]:
        if "default" in inp and (not job_order_object or shortname(inp["id"]) not in job_order_object):
            if not job_order_object:
                job_order_object = {}
            job_order_object[shortname(inp["id"])] = inp["default"]

    if not job_order_object and len(t.tool["inputs"]) > 0:
        parser.print_help()
        if toolparser:
            print "\nOptions for %s " % args.workflow
            toolparser.print_help()
        _logger.error("")
        _logger.error("Input object required")
        return 1

    return (job_order_object, input_basedir)


def main(args=None,
         executor=single_job_executor,
         makeTool=workflow.defaultMakeTool,
         selectResources=None,
         parser=None,
         stdin=sys.stdin,
         stdout=sys.stdout,
         stderr=sys.stderr):

    _logger.removeHandler(defaultStreamHandler)
    _logger.addHandler(logging.StreamHandler(stderr))

    if args is None:
        args = sys.argv[1:]

    if parser is None:
        parser = arg_parser()

    args = parser.parse_args(args)

    if args.quiet:
        _logger.setLevel(logging.WARN)
    if args.debug:
        _logger.setLevel(logging.DEBUG)

    pkg = pkg_resources.require("cwltool")
    if pkg:
        if args.version:
            print "%s %s" % (sys.argv[0], pkg[0].version)
            return 0
        else:
            _logger.info("%s %s", sys.argv[0], pkg[0].version)

    if not args.workflow:
        parser.print_help()
        _logger.error("")
        _logger.error("CWL document required")
        return 1

    try:
        t = load_tool(args.workflow, args.update, args.strict, makeTool, args.debug,
                      print_pre=args.print_pre,
                      print_rdf=args.print_rdf,
                      print_dot=args.print_dot,
                      rdf_serializer=args.rdf_serializer)
    except Exception as e:
        _logger.error("I'm sorry, I couldn't load this CWL file.\n%s", e, exc_info=(e if args.debug else False))
        return 1

    if type(t) == int:
        return t

    if args.tmp_outdir_prefix != 'tmp':
        # Use user defined temp directory (if it exists)
        args.tmp_outdir_prefix = os.path.abspath(args.tmp_outdir_prefix)
        if not os.path.exists(args.tmp_outdir_prefix):
            _logger.error("Intermediate output directory prefix doesn't exist, reverting to default")
            return 1

    if args.tmpdir_prefix != 'tmp':
        # Use user defined prefix (if the folder exists)
        args.tmpdir_prefix = os.path.abspath(args.tmpdir_prefix)
        if not os.path.exists(args.tmpdir_prefix):
            _logger.error("Temporary directory prefix doesn't exist.")
            return 1

    job_order_object = load_job_order(args, t, parser)

    if type(job_order_object) == int:
        return job_order_object

    try:
        out = executor(t, job_order_object[0],
                       job_order_object[1], args,
                       conformance_test=args.conformance_test,
                       dry_run=args.dry_run,
                       outdir=args.outdir,
                       tmp_outdir_prefix=args.tmp_outdir_prefix,
                       use_container=args.use_container,
                       preserve_environment=args.preserve_environment,
                       pull_image=args.enable_pull,
                       rm_container=args.rm_container,
                       tmpdir_prefix=args.tmpdir_prefix,
                       rm_tmpdir=args.rm_tmpdir,
                       makeTool=makeTool,
                       move_outputs=args.move_outputs,
                       select_resources=selectResources
                       )
        # This is the workflow output, it needs to be written
        stdout.write(json.dumps(out, indent=4))
        stdout.flush()
    except (validate.ValidationException) as e:
        _logger.error("Input object failed validation:\n%s", e, exc_info=(e if args.debug else False))
        return 1
    except workflow.WorkflowException as e:
        _logger.error("Workflow error:\n  %s", e, exc_info=(e if args.debug else False))
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
