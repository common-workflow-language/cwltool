#!/usr/bin/env python
from __future__ import absolute_import
<<<<<<< HEAD
import subprocess
=======
from __future__ import print_function

>>>>>>> origin/master
import argparse
import collections
import functools
import json
import logging
import os
import copy
import time
import ipdb
from time import gmtime, strftime
import sys
<<<<<<< HEAD
import tempfile
import prov.model as prov
import uuid
import datetime
from typing import (IO, Any, AnyStr, Callable, Dict, List, Sequence, Text, Tuple,
                    Union, cast)
import pkg_resources  # part of setuptools
import requests
import six
import string
=======
import warnings
from typing import (IO, Any, Callable, Dict, List, Text, Tuple,
                    Union, cast, Mapping, MutableMapping, Iterable)

import pkg_resources  # part of setuptools
>>>>>>> origin/master
import ruamel.yaml as yaml
import schema_salad.validate as validate
import six

from schema_salad.ref_resolver import Loader, file_uri, uri_file_path
from schema_salad.sourceline import strip_dup_lineno
from schema_salad.sourceline import SourceLine

<<<<<<< HEAD
from . import draft2tool
from . import workflow
from .builder import Builder
=======
from . import command_line_tool, workflow
from .argparser import arg_parser, generate_parser, DEFAULT_TMP_PREFIX
>>>>>>> origin/master
from .cwlrdf import printdot, printrdf
from .errors import UnsupportedRequirement, WorkflowException
from .executors import SingleJobExecutor, MultithreadedJobExecutor
from .load_tool import (FetcherConstructorType, resolve_tool_uri,
                        fetch_document, make_tool, validate_document, jobloaderctx,
                        resolve_overrides, load_overrides)
from .loghandler import defaultStreamHandler
from .mutation import MutationManager
from .pack import pack
<<<<<<< HEAD
from .pathmapper import (adjustDirObjs, adjustFileObjs, get_listing,
                         trim_listing, visit_class)
from .provenance import create_ro
from .process import (Process, cleanIntermediate, normalizeFilesDirs,
                      relocateOutputs, scandeps, shortname, use_custom_schema,
=======
from .pathmapper import (adjustDirObjs, trim_listing, visit_class)
from .process import (Process, normalizeFilesDirs,
                      scandeps, shortname, use_custom_schema,
>>>>>>> origin/master
                      use_standard_schema)
from .resolver import ga4gh_tool_registries, tool_resolver
from .software_requirements import (DependenciesConfiguration,
                                    get_container_from_software_requirements)
from .stdfsaccess import StdFsAccess
from .update import ALLUPDATES, UPDATES
from .utils import onWindows, windows_default_container_id
<<<<<<< HEAD
from ruamel.yaml.comments import Comment, CommentedSeq, CommentedMap

_logger = logging.getLogger("cwltool")

#Adding default namespaces
document = prov.ProvDocument()
engineUUID=""
activity_workflowRun={}
defaultStreamHandler = logging.StreamHandler()
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)
#adding the SoftwareAgent to PROV document
engineUUID="engine:"+str(uuid.uuid4())
#defining workflow level run ID
WorkflowRunUUID=str(uuid.uuid4())
WorkflowRunID="run:"+WorkflowRunUUID


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

    parser.add_argument("--provenance",
                        help="Save provenance to specified folder as a Research Object that capture and aggregate workflow execution and data products.",
                        type=Text)

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
    exgroup.add_argument("--print-dot", action="store_true",
                         help="Print workflow visualization in graphviz format and exit")
    exgroup.add_argument("--print-pre", action="store_true", help="Print CWL document after preprocessing.")
    exgroup.add_argument("--print-deps", action="store_true", help="Print CWL document dependencies.")
    exgroup.add_argument("--print-input-deps", action="store_true", help="Print input object document dependencies.")
    exgroup.add_argument("--pack", action="store_true", help="Combine components into single document and print.")
    exgroup.add_argument("--version", action="store_true", help="Print version and exit")
    exgroup.add_argument("--validate", action="store_true", help="Validate CWL document only.")
    exgroup.add_argument("--print-supported-versions", action="store_true", help="Print supported CWL specs.")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--strict", action="store_true",
                         help="Strict validation (unrecognized or out of place fields are error)",
                         default=True, dest="strict")
    exgroup.add_argument("--non-strict", action="store_false", help="Lenient validation (ignore unrecognized fields)",
                         default=True, dest="strict")

    parser.add_argument("--skip-schemas", action="store_true",
            help="Skip loading of schemas", default=True, dest="skip_schemas")

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--verbose", action="store_true", help="Default logging")
    exgroup.add_argument("--quiet", action="store_true", help="Only print warnings and errors.")
    exgroup.add_argument("--debug", action="store_true", help="Print even more logging")

    parser.add_argument("--js-console", action="store_true", help="Enable javascript console output")

    dependency_resolvers_configuration_help = argparse.SUPPRESS
    dependencies_directory_help = argparse.SUPPRESS
    use_biocontainers_help = argparse.SUPPRESS
    conda_dependencies = argparse.SUPPRESS

    if SOFTWARE_REQUIREMENTS_ENABLED:
        dependency_resolvers_configuration_help = "Dependency resolver configuration file describing how to adapt 'SoftwareRequirement' packages to current system."
        dependencies_directory_help = "Defaut root directory used by dependency resolvers configuration."
        use_biocontainers_help = "Use biocontainers for tools without an explicitly annotated Docker container."
        conda_dependencies = "Short cut to use Conda to resolve 'SoftwareRequirement' packages."

    parser.add_argument("--beta-dependency-resolvers-configuration", default=None, help=dependency_resolvers_configuration_help)
    parser.add_argument("--beta-dependencies-directory", default=None, help=dependencies_directory_help)
    parser.add_argument("--beta-use-biocontainers", default=None, help=use_biocontainers_help, action="store_true")
    parser.add_argument("--beta-conda-dependencies", default=None, help=conda_dependencies, action="store_true")

    parser.add_argument("--tool-help", action="store_true", help="Print command line help for tool")

    parser.add_argument("--relative-deps", choices=['primary', 'cwd'],
                        default="primary", help="When using --print-deps, print paths "
                                                "relative to primary file or current working directory.")

    parser.add_argument("--enable-dev", action="store_true",
                        help="Enable loading and running development versions "
                             "of CWL spec.", default=False)

    parser.add_argument("--enable-ext", action="store_true",
                        help="Enable loading and running cwltool extensions "
                             "to CWL spec.", default=False)

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

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--enable-ga4gh-tool-registry", action="store_true", help="Enable resolution using GA4GH tool registry API",
                        dest="enable_ga4gh_tool_registry", default=True)
    exgroup.add_argument("--disable-ga4gh-tool-registry", action="store_false", help="Disable resolution using GA4GH tool registry API",
                        dest="enable_ga4gh_tool_registry", default=True)

    parser.add_argument("--add-ga4gh-tool-registry", action="append", help="Add a GA4GH tool registry endpoint to use for resolution, default %s" % ga4gh_tool_registries,
                        dest="ga4gh_tool_registries", default=[])

    parser.add_argument("--on-error",
                        help="Desired workflow behavior when a step fails.  One of 'stop' or 'continue'. "
                             "Default is 'stop'.", default="stop", choices=("stop", "continue"))

    exgroup = parser.add_mutually_exclusive_group()
    exgroup.add_argument("--compute-checksum", action="store_true", default=True,
                         help="Compute checksum of contents while collecting outputs",
                         dest="compute_checksum")
    exgroup.add_argument("--no-compute-checksum", action="store_false",
                         help="Do not compute checksum of contents while collecting outputs",
                         dest="compute_checksum")

    parser.add_argument("--relax-path-checks", action="store_true",
                        default=False, help="Relax requirements on path names to permit "
                        "spaces and hash characters.", dest="relax_path_checks")
    exgroup.add_argument("--make-template", action="store_true",
                         help="Generate a template input object")

    parser.add_argument("--force-docker-pull", action="store_true",
                        default=False, help="Pull latest docker image even if"
                                            " it is locally present", dest="force_docker_pull")
    parser.add_argument("--no-read-only", action="store_true",
                        default=False, help="Do not set root directoy in the"
                                            " container as read-only", dest="no_read_only")
    parser.add_argument("workflow", type=Text, nargs="?", default=None)
    parser.add_argument("job_order", nargs=argparse.REMAINDER)

    return parser
#ipdb.set_trace()
#for retrospective details. This is where we should make all the changes and capture provenance.
=======

_logger = logging.getLogger("cwltool")


>>>>>>> origin/master
def single_job_executor(t,  # type: Process
                        job_order_object,  # type: Dict[Text, Any]
                        **kwargs # type: Any
                        ):
    # type: (...) -> Tuple[Dict[Text, Any], Text]
<<<<<<< HEAD
    final_output = []
    final_status = []

    reference_locations={}

    ProvActivity_dict={}
    def output_callback(out, processStatus):
        final_status.append(processStatus)
        final_output.append(out)

    if "basedir" not in kwargs:
        raise WorkflowException("Must provide 'basedir' in kwargs")
    output_dirs = set()
    finaloutdir = os.path.abspath(kwargs.get("outdir")) if kwargs.get("outdir") else None
    kwargs["outdir"] = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"]) if kwargs.get(
        "tmp_outdir_prefix") else tempfile.mkdtemp()
    output_dirs.add(kwargs["outdir"])

    kwargs["mutation_manager"] = MutationManager()
#capture requirements in PROV document.
    jobReqs = None
    if "cwl:requirements" in job_order_object:
        jobReqs = job_order_object["cwl:requirements"]
    elif ("cwl:defaults" in t.metadata and "cwl:requirements" in t.metadata["cwl:defaults"]):
        jobReqs = t.metadata["cwl:defaults"]["cwl:requirements"]
    if jobReqs:
        for req in jobReqs:
            t.requirements.append(req)
    jobiter = t.job(job_order_object,
                    output_callback,
                    **kwargs)
    try:
        for r in jobiter: #its each step of the workflow
            ro = kwargs.get("ro")
            if r: #for every step, a uuid as ProcessRunID is generated for provenance record
                builder = kwargs.get("builder", None)  # type: Builder
                if builder is not None:
                    r.builder = builder
                if r.outdir:
                    output_dirs.add(r.outdir)
                if ro:
                    #here we are recording provenance of each subprocess of the workflow
                    if ".cwl" in getattr(r, "name"): #for prospective provenance
                        steps=[]
                        for s in r.steps:
                            stepname="wf:main/"+str(s.name)[5:]
                            steps.append(stepname)
                            document.entity(stepname, {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan"})
                        #create prospective provenance recording for the workflow
                        document.entity("wf:main", {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan", "wfdesc:hasSubProcess=":str(steps),  "prov:label":"Prospective provenance"})
                        customised_job={} #new job object for RO
                        for e, i in enumerate(r.tool["inputs"]):
                            with SourceLine(r.tool["inputs"], e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                                iid = shortname(i["id"])
                                if iid in job_order_object:
                                    customised_job[iid]= copy.deepcopy(job_order_object[iid]) #add the input element in dictionary for provenance
                                elif "default" in i:
                                    customised_job[iid]= copy.deepcopy(i["default"]) #add the defualt elements in the dictionary for provenance
                                else:
                                    raise WorkflowException(
                                        u"Input '%s' not in input object and does not have a default value." % (i["id"]))
                        ##create master-job.json and returns a dictionary with workflow level identifiers as keys and locations or actual values of the attributes as values.
                        relativised_input_object=ro.create_job(customised_job, kwargs) #call the method to generate a file with customised job
                        for key, value in relativised_input_object.items():
                            strvalue=str(value)
                            if "data" in strvalue:
                                shahash="data:"+value.split("/")[-1]
                                rel_path=value[3:]
                                reference_locations[job_order_object[key]["location"]]=relativised_input_object[key][11:]
                                document.entity(shahash, {prov.PROV_TYPE:"wfprov:Artifact"})
                                #document.specializationOf(rel_path, shahash) NOTE:THIS NEEDS FIXING as it required both params as entities.
                            else:
                                ArtefactValue="data:"+strvalue
                                document.entity(ArtefactValue, {prov.PROV_TYPE:"wfprov:Artifact"})
                if ".cwl" not in getattr(r, "name"):
                    if ro:
                        ProcessRunID="run:"+str(uuid.uuid4())
                        #each subprocess is defined as an activity()
                        provLabel="Run of workflow/packed.cwl#main/"+str(r.name)
                        ProcessProvActivity = document.activity(ProcessRunID, None, None, {prov.PROV_TYPE: "wfprov:ProcessRun", "prov:label": provLabel})
                        if hasattr(r, 'name') and ".cwl" not in getattr(r, "name"):
                            document.wasAssociatedWith(ProcessRunID, engineUUID, str("wf:main/"+r.name))
                        document.wasStartedBy(ProcessRunID, None, WorkflowRunID, datetime.datetime.now(), None, None)
                        #this is where you run each step. so start and end time for the step
                        r.run(document, WorkflowRunID, ProcessProvActivity, reference_locations, **kwargs)
                    else:
                        r.run(**kwargs)
                    #capture workflow level outputs in the prov doc
                    if ro:
                        for eachOutput in final_output:
                            for key, value in eachOutput.items():
                                outputProvRole="wf:main"+"/"+str(key)
                                output_checksum="data:"+str(value["checksum"][5:])
                                document.entity(output_checksum, {prov.PROV_TYPE:"wfprov:Artifact"})
                                document.wasGeneratedBy(output_checksum, WorkflowRunID, datetime.datetime.now(), None, {"prov:role":outputProvRole })
            else:
                _logger.error("Workflow cannot make any more progress.")
                break
    except WorkflowException:
        raise
    except Exception as e:
        _logger.exception("Got workflow error")
        raise WorkflowException(Text(e))
    if final_output and final_output[0] and finaloutdir:
        final_output[0] = relocateOutputs(final_output[0], finaloutdir,
                                          output_dirs, kwargs.get("move_outputs"),
                                          kwargs["make_fs_access"](""))
    if kwargs.get("rm_tmpdir"):
        cleanIntermediate(output_dirs)
    if final_output and final_status:
        return (final_output[0], final_status[0])
    else:
        return (None, "permanentFail")



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
                 "location": file_uri(str(os.path.abspath(cast(AnyStr, values))))})


class FSAppendAction(argparse.Action):
    objclass = None  # type: Text

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # type: (List[Text], Text, Any, **Any) -> None
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(FSAppendAction, self).__init__(option_strings, dest, **kwargs)
=======
    warnings.warn("Use of single_job_executor function is deprecated. "
                  "Use cwltool.executors.SingleJobExecutor class instead", DeprecationWarning)
    executor = SingleJobExecutor()
    return executor(t, job_order_object, **kwargs)
>>>>>>> origin/master


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


<<<<<<< HEAD

def load_job_order(args, t, stdin, print_input_deps=False, provArgs= None, relative_deps=False,
                   stdout=sys.stdout, make_fs_access=None, fetcher_constructor=None):
    # type: (argparse.Namespace, Process, IO[Any], bool, bool, IO[Any], Callable[[Text], StdFsAccess], Callable[[Dict[Text, Text], requests.sessions.Session], Fetcher]) -> Union[int, Tuple[Dict[Text, Any], Text]]
=======
def load_job_order(args,   # type: argparse.Namespace
                   stdin,  # type: IO[Any]
                   fetcher_constructor,  # Fetcher
                   overrides,  # type: List[Dict[Text, Any]]
                   tool_file_uri  # type: Text
):
    # type: (...) -> Tuple[Dict[Text, Any], Text, Loader]
>>>>>>> origin/master

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
            toolparser.print_help()
        _logger.error("")
        _logger.error("Input object required, use --help for details")
<<<<<<< HEAD
        return 1
    if provArgs:
        inputforProv=printdeps(job_order_object, loader, stdout, relative_deps, "", basedir=file_uri(input_basedir + "/"))
=======
        exit(1)

>>>>>>> origin/master
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
<<<<<<< HEAD
    if provArgs:
        return (job_order_object, input_basedir, loader, inputforProv)
    else:
        return (job_order_object, input_basedir, loader)
=======

    return job_order_object
>>>>>>> origin/master


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
        absdeps=copy.deepcopy(deps)
        visit_class(deps, ("File", "Directory"), functools.partial(makeRelative, base))

    stdout.write(json.dumps(absdeps, indent=4))
    return (deps, absdeps)

def print_pack(document_loader, processobj, uri, metadata):
    # type: (Loader, Union[Dict[Text, Any], List[Dict[Text, Any]]], Text, Dict[Text, Any]) -> str
    packed = pack(document_loader, processobj, uri, metadata)
    if len(packed["$graph"]) > 1:
        return json.dumps(packed, indent=4)
    else:
        return json.dumps(packed["$graph"][0], indent=4)

def generate_provDoc():
    document.add_namespace('wfprov', 'http://purl.org/wf4ever/wfprov#')
    document.add_namespace('prov', 'http://www.w3.org/ns/prov')
    document.add_namespace('wfdesc', 'http://purl.org/wf4ever/wfdesc#')
    document.add_namespace('run', 'urn:uuid:')
    document.add_namespace('engine', 'urn:uuid4:')
    document.add_namespace('data', 'urn:hash:sha1')
    cwlversionProv="cwltool "+ str(versionstring().split()[-1])
    roIdentifierWorkflow="app://"+WorkflowRunUUID+"/workflow/packed.cwl#"
    document.add_namespace("wf", roIdentifierWorkflow)
    roIdentifierInput="app://"+WorkflowRunUUID+"/workflow/master-job.json#"
    document.add_namespace("input", roIdentifierInput)
    #Get cwltool version
    cwlversionProv="cwltool "+ str(versionstring().split()[-1])
    document.agent(engineUUID, {prov.PROV_TYPE: "prov:SoftwareAgent", "prov:type": "wfprov:WorkflowEngine", "prov:label": cwlversionProv})
    #define workflow run level activity
    activity_workflowRun = document.activity(WorkflowRunID, datetime.datetime.now(), None, {prov.PROV_TYPE: "wfprov:WorkflowRun", "prov:label": "Run of workflow/packed.cwl#main"})
    #association between SoftwareAgent and WorkflowRun
    mainWorkflow = "wf:main"
    document.wasAssociatedWith(WorkflowRunID, engineUUID, mainWorkflow)

#version of CWLtool used to execute the workflow.
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
#ipdb.set_trace()
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
    #input_basedir=''
    try:
        if args is None:
            if argsl is None:
                argsl = sys.argv[1:]
            args = arg_parser().parse_args(argsl)
        #ipdb.set_trace()
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
<<<<<<< HEAD
                     'make_template': False,
                     'provenance': None,
                     'ro': None
=======
                                   'make_template': False,
                                   'overrides': None
>>>>>>> origin/master
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
<<<<<<< HEAD
        #call function from provenance.py if the provenance flag is enabled.
        if args.provenance:
            args.ro = create_ro(tmpPrefix=args.tmpdir_prefix)
=======

        uri, tool_file_uri = resolve_tool_uri(args.workflow,
                                              resolver=resolver,
                                              fetcher_constructor=fetcher_constructor)

        overrides = []  # type: List[Dict[Text, Any]]

>>>>>>> origin/master
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
<<<<<<< HEAD
                                    skip_schemas=args.skip_schemas)

            if args.pack:
                stdout.write(print_pack(document_loader, processobj, uri, metadata))
                return 0
            if args.provenance: # Can't really be combined with args.pack at same time
                packedWorkflow=args.ro.packed_workflow(print_pack(document_loader, processobj, uri, metadata))
                #extract path to include in PROV document
                packedWorkflowpath_without_main=str(packedWorkflow).split("/")[-2]+"/"+str(packedWorkflow).split("/")[-1]
                packedWorkflowPath=str(packedWorkflow).split("/")[-2]+"/"+str(packedWorkflow).split("/")[-1]+"#main"
=======
                                    skip_schemas=args.skip_schemas,
                                    overrides=overrides)

>>>>>>> origin/master
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

<<<<<<< HEAD
        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir", "provenance"):
            if getattr(args, dirprefix) and getattr(args, dirprefix) != 'tmp':
=======
        # If on MacOS platform, TMPDIR must be set to be under one of the shared volumes in Docker for Mac
        # More info: https://dockstore.org/docs/faq
        if sys.platform == "darwin":
            tmp_prefix = "tmp_outdir_prefix"
            default_mac_path = "/private/tmp/docker_tmp"
            if getattr(args, tmp_prefix) and getattr(args, tmp_prefix) == DEFAULT_TMP_PREFIX:
                setattr(args, tmp_prefix, default_mac_path)

        for dirprefix in ("tmpdir_prefix", "tmp_outdir_prefix", "cachedir"):
            if getattr(args, dirprefix) and getattr(args, dirprefix) != DEFAULT_TMP_PREFIX:
>>>>>>> origin/master
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
<<<<<<< HEAD

            if args.provenance and args.ro:
                generate_provDoc()

            if job_order_object is None:
                    job_order_object = load_job_order(args, tool, stdin,
                                                      print_input_deps=args.print_input_deps,
                                                      relative_deps=args.relative_deps,
                                                      provArgs=args.ro,
                                                      stdout=stdout,
                                                      make_fs_access=make_fs_access,
                                                      fetcher_constructor=fetcher_constructor)

        except SystemExit as e:
            return e.code

=======
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
>>>>>>> origin/master

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

            # prov: This is the workflow output, it needs to be copied in RO
            if out is not None:
                #prov: closing the RO after writing everything and removing any temporary files
                if args.provenance and args.ro:
                    args.ro.add_output(out, args.provenance)
                    #args.ro.close(args.provenance)


                def locToPath(p):
                    for field in ("path", "nameext", "nameroot", "dirname"):
                        if field in p:
                            del p[field]
                    if p["location"].startswith("file://"):
                        p["path"] = uri_file_path(p["location"])

                visit_class(out, ("File", "Directory"), locToPath)

                # Unsetting the Generation from final output object
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
        _logger.info(u"End Time:  %s", time.strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))

        if hasattr(args, "ro") and args.provenance and args.rm_tmpdir:
            document.wasEndedBy(WorkflowRunID, None, WorkflowRunID, datetime.datetime.now())
            #adding all related cwl files to RO
            ProvDependencies=printdeps(workflowobj, document_loader, stdout, args.relative_deps, uri)
            args.ro.snapshot_generation(ProvDependencies[1])
            args.ro.snapshot_generation(job_order_object[3][1])

            #adding prov profile and graphs to RO
            args.ro.add_provProfile(document)
            args.ro.close(args.provenance)

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
