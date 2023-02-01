"""Command line argument parsing for cwltool."""

import argparse
import os
import urllib
from typing import (
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

from .loghandler import _logger
from .process import Process, shortname
from .resolver import ga4gh_tool_registries
from .software_requirements import SOFTWARE_REQUIREMENTS_ENABLED
from .utils import DEFAULT_TMP_PREFIX


def arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reference executor for Common Workflow Language standards. "
        "Not for production use."
    )
    parser.add_argument("--basedir", type=str)
    parser.add_argument(
        "--outdir",
        type=str,
        default=os.path.abspath("."),
        help="Output directory. The default is the current directory.",
    )

    parser.add_argument(
        "--log-dir",
        type=str,
        default="",
        help="Log your tools stdout/stderr to this location outside of container "
        "This will only log stdout/stderr if you specify stdout/stderr in their "
        "respective fields or capture it as an output",
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="[experimental] Run jobs in parallel. ",
    )
    envgroup = parser.add_mutually_exclusive_group()
    envgroup.add_argument(
        "--preserve-environment",
        type=str,
        action="append",
        help="Preserve specific environment variable when running "
        "CommandLineTools. May be provided multiple times. By default PATH is "
        "preserved when not running in a container.",
        metavar="ENVVAR",
        default=[],
        dest="preserve_environment",
    )
    envgroup.add_argument(
        "--preserve-entire-environment",
        action="store_true",
        help="Preserve all environment variables when running CommandLineTools "
        "without a software container.",
        default=False,
        dest="preserve_entire_environment",
    )

    containergroup = parser.add_mutually_exclusive_group()
    containergroup.add_argument(
        "--rm-container",
        action="store_true",
        default=True,
        help="Delete Docker container used by jobs after they exit (default)",
        dest="rm_container",
    )

    containergroup.add_argument(
        "--leave-container",
        action="store_false",
        default=True,
        help="Do not delete Docker container used by jobs after they exit",
        dest="rm_container",
    )

    cidgroup = parser.add_argument_group(
        "Options for recording the Docker container identifier into a file."
    )
    cidgroup.add_argument(
        # Disabled as containerid is now saved by default
        "--record-container-id",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
        dest="record_container_id",
    )

    cidgroup.add_argument(
        "--cidfile-dir",
        type=str,
        help="Store the Docker container ID into a file in the specified directory.",
        default=None,
        dest="cidfile_dir",
    )

    cidgroup.add_argument(
        "--cidfile-prefix",
        type=str,
        help="Specify a prefix to the container ID filename. "
        "Final file name will be followed by a timestamp. "
        "The default is no prefix.",
        default=None,
        dest="cidfile_prefix",
    )

    parser.add_argument(
        "--tmpdir-prefix",
        type=str,
        help="Path prefix for temporary directories. If --tmpdir-prefix is not "
        "provided, then the prefix for temporary directories is influenced by "
        "the value of the TMPDIR, TEMP, or TMP environment variables. Taking "
        "those into consideration, the current default is {}.".format(DEFAULT_TMP_PREFIX),
        default=DEFAULT_TMP_PREFIX,
    )

    intgroup = parser.add_mutually_exclusive_group()
    intgroup.add_argument(
        "--tmp-outdir-prefix",
        type=str,
        help="Path prefix for intermediate output directories. Defaults to the "
        "value of --tmpdir-prefix.",
        default="",
    )

    intgroup.add_argument(
        "--cachedir",
        type=str,
        default="",
        help="Directory to cache intermediate workflow outputs to avoid "
        "recomputing steps. Can be very helpful in the development and "
        "troubleshooting of CWL documents.",
    )

    tmpgroup = parser.add_mutually_exclusive_group()
    tmpgroup.add_argument(
        "--rm-tmpdir",
        action="store_true",
        default=True,
        help="Delete intermediate temporary directories (default)",
        dest="rm_tmpdir",
    )

    tmpgroup.add_argument(
        "--leave-tmpdir",
        action="store_false",
        default=True,
        help="Do not delete intermediate temporary directories",
        dest="rm_tmpdir",
    )

    outgroup = parser.add_mutually_exclusive_group()
    outgroup.add_argument(
        "--move-outputs",
        action="store_const",
        const="move",
        default="move",
        help="Move output files to the workflow output directory and delete "
        "intermediate output directories (default).",
        dest="move_outputs",
    )

    outgroup.add_argument(
        "--leave-outputs",
        action="store_const",
        const="leave",
        default="move",
        help="Leave output files in intermediate output directories.",
        dest="move_outputs",
    )

    outgroup.add_argument(
        "--copy-outputs",
        action="store_const",
        const="copy",
        default="move",
        help="Copy output files to the workflow output directory and don't "
        "delete intermediate output directories.",
        dest="move_outputs",
    )

    pullgroup = parser.add_mutually_exclusive_group()
    pullgroup.add_argument(
        "--enable-pull",
        default=True,
        action="store_true",
        help="Try to pull Docker images",
        dest="pull_image",
    )

    pullgroup.add_argument(
        "--disable-pull",
        default=True,
        action="store_false",
        help="Do not try to pull Docker images",
        dest="pull_image",
    )

    parser.add_argument(
        "--rdf-serializer",
        help="Output RDF serialization format used by --print-rdf (one of "
        "turtle (default), n3, nt, xml)",
        default="turtle",
    )

    parser.add_argument(
        "--eval-timeout",
        help="Time to wait for a Javascript expression to evaluate before giving "
        "an error, default 60s.",
        type=float,
        default=60,
    )

    provgroup = parser.add_argument_group(
        "Options for recording provenance information of the execution"
    )
    provgroup.add_argument(
        "--provenance",
        help="Save provenance to specified folder as a "
        "Research Object that captures and aggregates "
        "workflow execution and data products.",
        type=str,
    )

    provgroup.add_argument(
        "--enable-user-provenance",
        default=False,
        action="store_true",
        help="Record user account info as part of provenance.",
        dest="user_provenance",
    )
    provgroup.add_argument(
        "--disable-user-provenance",
        default=False,
        action="store_false",
        help="Do not record user account info in provenance.",
        dest="user_provenance",
    )
    provgroup.add_argument(
        "--enable-host-provenance",
        default=False,
        action="store_true",
        help="Record host info as part of provenance.",
        dest="host_provenance",
    )
    provgroup.add_argument(
        "--disable-host-provenance",
        default=False,
        action="store_false",
        help="Do not record host info in provenance.",
        dest="host_provenance",
    )
    provgroup.add_argument(
        "--orcid",
        help="Record user ORCID identifier as part of "
        "provenance, e.g. https://orcid.org/0000-0002-1825-0097 "
        "or 0000-0002-1825-0097. Alternatively the environment variable "
        "ORCID may be set.",
        dest="orcid",
        default=os.environ.get("ORCID", ""),
        type=str,
    )
    provgroup.add_argument(
        "--full-name",
        help="Record full name of user as part of provenance, "
        "e.g. Josiah Carberry. You may need to use shell quotes to preserve "
        "spaces. Alternatively the environment variable CWL_FULL_NAME may "
        "be set.",
        dest="cwl_full_name",
        default=os.environ.get("CWL_FULL_NAME", ""),
        type=str,
    )

    printgroup = parser.add_mutually_exclusive_group()
    printgroup.add_argument(
        "--print-rdf",
        action="store_true",
        help="Print corresponding RDF graph for workflow and exit",
    )
    printgroup.add_argument(
        "--print-dot",
        action="store_true",
        help="Print workflow visualization in graphviz format and exit",
    )
    printgroup.add_argument(
        "--print-pre",
        action="store_true",
        help="Print CWL document after preprocessing.",
    )
    printgroup.add_argument(
        "--print-deps", action="store_true", help="Print CWL document dependencies."
    )
    printgroup.add_argument(
        "--print-input-deps",
        action="store_true",
        help="Print input object document dependencies.",
    )
    printgroup.add_argument(
        "--pack",
        action="store_true",
        help="Combine components into single document and print.",
    )
    printgroup.add_argument("--version", action="store_true", help="Print version and exit")
    printgroup.add_argument("--validate", action="store_true", help="Validate CWL document only.")
    printgroup.add_argument(
        "--print-supported-versions",
        action="store_true",
        help="Print supported CWL specs.",
    )
    printgroup.add_argument(
        "--print-subgraph",
        action="store_true",
        help="Print workflow subgraph that will execute. Can combined with "
        "--target or --single-step",
    )
    printgroup.add_argument(
        "--print-targets", action="store_true", help="Print targets (output parameters)"
    )
    printgroup.add_argument(
        "--make-template", action="store_true", help="Generate a template input object"
    )

    strictgroup = parser.add_mutually_exclusive_group()
    strictgroup.add_argument(
        "--strict",
        action="store_true",
        help="Strict validation (unrecognized or out of place fields are error)",
        default=True,
        dest="strict",
    )
    strictgroup.add_argument(
        "--non-strict",
        action="store_false",
        help="Lenient validation (ignore unrecognized fields)",
        default=True,
        dest="strict",
    )

    parser.add_argument(
        "--skip-schemas",
        action="store_true",
        help="Skip loading of schemas",
        default=False,
        dest="skip_schemas",
    )

    doccachegroup = parser.add_mutually_exclusive_group()
    doccachegroup.add_argument(
        "--no-doc-cache",
        action="store_false",
        help="Disable disk cache for documents loaded over HTTP",
        default=True,
        dest="doc_cache",
    )
    doccachegroup.add_argument(
        "--doc-cache",
        action="store_true",
        help="Enable disk cache for documents loaded over HTTP",
        default=True,
        dest="doc_cache",
    )

    volumegroup = parser.add_mutually_exclusive_group()
    volumegroup.add_argument("--verbose", action="store_true", help="Default logging")
    volumegroup.add_argument("--quiet", action="store_true", help="Only print warnings and errors.")
    volumegroup.add_argument("--debug", action="store_true", help="Print even more logging")

    parser.add_argument(
        "--write-summary",
        "-w",
        type=str,
        help="Path to write the final output JSON object to. Default is stdout.",
        default="",
        dest="write_summary",
    )

    parser.add_argument(
        "--strict-memory-limit",
        action="store_true",
        help="When running with "
        "software containers and the Docker engine, pass either the "
        "calculated memory allocation from ResourceRequirements or the "
        "default of 1 gigabyte to Docker's --memory option.",
    )

    parser.add_argument(
        "--strict-cpu-limit",
        action="store_true",
        help="When running with "
        "software containers and the Docker engine, pass either the "
        "calculated cpu allocation from ResourceRequirements or the "
        "default of 1 core to Docker's --cpu option. "
        "Requires docker version >= v1.13.",
    )

    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Add timestamps to the errors, warnings, and notifications.",
    )
    parser.add_argument(
        "--js-console", action="store_true", help="Enable javascript console output"
    )
    parser.add_argument(
        "--disable-js-validation",
        action="store_true",
        help="Disable javascript validation.",
    )
    parser.add_argument(
        "--js-hint-options-file",
        type=str,
        help="File of options to pass to jshint. "
        'This includes the added option "includewarnings". ',
    )
    dockergroup = parser.add_mutually_exclusive_group()
    dockergroup.add_argument(
        "--user-space-docker-cmd",
        metavar="CMD",
        help="(Linux/OS X only) Specify the path to udocker. Implies --udocker",
    )
    dockergroup.add_argument(
        "--udocker",
        help="(Linux/OS X only) Use the udocker runtime for running containers "
        "(equivalent to --user-space-docker-cmd=udocker).",
        action="store_const",
        const="udocker",
        dest="user_space_docker_cmd",
    )

    dockergroup.add_argument(
        "--singularity",
        action="store_true",
        default=False,
        help="[experimental] Use "
        "Singularity runtime for running containers. "
        "Requires Singularity v2.6.1+ and Linux with kernel "
        "version v3.18+ or with overlayfs support "
        "backported.",
    )
    dockergroup.add_argument(
        "--podman",
        action="store_true",
        default=False,
        help="[experimental] Use " "Podman runtime for running containers. ",
    )
    dockergroup.add_argument(
        "--no-container",
        action="store_false",
        default=True,
        help="Do not execute jobs in a "
        "Docker container, even when `DockerRequirement` "
        "is specified under `hints`.",
        dest="use_container",
    )

    dependency_resolvers_configuration_help = argparse.SUPPRESS
    dependencies_directory_help = argparse.SUPPRESS
    use_biocontainers_help = argparse.SUPPRESS
    conda_dependencies = argparse.SUPPRESS

    if SOFTWARE_REQUIREMENTS_ENABLED:
        dependency_resolvers_configuration_help = (
            "Dependency resolver "
            "configuration file describing how to adapt 'SoftwareRequirement' "
            "packages to current system."
        )
        dependencies_directory_help = (
            "Default root directory used by dependency resolvers configuration."
        )
        use_biocontainers_help = (
            "Use biocontainers for tools without an " "explicitly annotated Docker container."
        )
        conda_dependencies = "Short cut to use Conda to resolve 'SoftwareRequirement' packages."

    parser.add_argument(
        "--beta-dependency-resolvers-configuration",
        default=None,
        help=dependency_resolvers_configuration_help,
    )
    parser.add_argument(
        "--beta-dependencies-directory", default=None, help=dependencies_directory_help
    )
    parser.add_argument(
        "--beta-use-biocontainers",
        default=None,
        help=use_biocontainers_help,
        action="store_true",
    )
    parser.add_argument(
        "--beta-conda-dependencies",
        default=None,
        help=conda_dependencies,
        action="store_true",
    )

    parser.add_argument("--tool-help", action="store_true", help="Print command line help for tool")

    parser.add_argument(
        "--relative-deps",
        choices=["primary", "cwd"],
        default="primary",
        help="When using --print-deps, print paths "
        "relative to primary file or current working directory.",
    )

    parser.add_argument(
        "--enable-dev",
        action="store_true",
        help="Enable loading and running unofficial development versions of " "the CWL standards.",
        default=False,
    )

    parser.add_argument(
        "--enable-ext",
        action="store_true",
        help="Enable loading and running 'cwltool:' extensions to the CWL standards.",
        default=False,
    )

    colorgroup = parser.add_mutually_exclusive_group()
    colorgroup.add_argument(
        "--enable-color",
        action="store_true",
        help="Enable logging color (default enabled)",
        default=True,
    )
    colorgroup.add_argument(
        "--disable-color",
        action="store_false",
        dest="enable_color",
        help="Disable colored logging (default false)",
    )

    parser.add_argument(
        "--default-container",
        help="Specify a default software container to use for any "
        "CommandLineTool without a DockerRequirement.",
    )
    parser.add_argument(
        "--no-match-user",
        action="store_true",
        help="Disable passing the current uid to `docker run --user`",
    )
    parser.add_argument(
        "--custom-net",
        type=str,
        help="Passed to `docker run` as the '--net' parameter when "
        "NetworkAccess is true, which is its default setting.",
    )
    parser.add_argument(
        "--disable-validate",
        dest="do_validate",
        action="store_false",
        default=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fast-parser",
        dest="fast_parser",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )

    reggroup = parser.add_mutually_exclusive_group()
    reggroup.add_argument(
        "--enable-ga4gh-tool-registry",
        action="store_true",
        help="Enable tool resolution using GA4GH tool registry API",
        dest="enable_ga4gh_tool_registry",
        default=True,
    )
    reggroup.add_argument(
        "--disable-ga4gh-tool-registry",
        action="store_false",
        help="Disable tool resolution using GA4GH tool registry API",
        dest="enable_ga4gh_tool_registry",
        default=True,
    )

    parser.add_argument(
        "--add-ga4gh-tool-registry",
        action="append",
        help="Add a GA4GH tool registry endpoint to use for resolution, default %s"
        % ga4gh_tool_registries,
        dest="ga4gh_tool_registries",
        default=[],
    )

    parser.add_argument(
        "--on-error",
        help="Desired workflow behavior when a step fails.  One of 'stop' (do "
        "not submit any more steps) or 'continue' (may submit other steps that "
        "are not downstream from the error). Default is 'stop'.",
        default="stop",
        choices=("stop", "continue"),
    )

    checkgroup = parser.add_mutually_exclusive_group()
    checkgroup.add_argument(
        "--compute-checksum",
        action="store_true",
        default=True,
        help="Compute checksum of contents while collecting outputs",
        dest="compute_checksum",
    )
    checkgroup.add_argument(
        "--no-compute-checksum",
        action="store_false",
        help="Do not compute checksum of contents while collecting outputs",
        dest="compute_checksum",
    )

    parser.add_argument(
        "--relax-path-checks",
        action="store_true",
        default=False,
        help="Relax requirements on path names to permit " "spaces and hash characters.",
        dest="relax_path_checks",
    )

    parser.add_argument(
        "--force-docker-pull",
        action="store_true",
        default=False,
        help="Pull latest software container image even if it is locally present",
        dest="force_docker_pull",
    )
    parser.add_argument(
        "--no-read-only",
        action="store_true",
        default=False,
        help="Do not set root directory in the container as read-only",
        dest="no_read_only",
    )

    parser.add_argument(
        "--overrides",
        type=str,
        default=None,
        help="Read process requirement overrides from file.",
    )

    subgroup = parser.add_mutually_exclusive_group()
    subgroup.add_argument(
        "--target",
        "-t",
        action="append",
        help="Only execute steps that contribute to listed targets (can be "
        "provided more than once).",
    )
    subgroup.add_argument(
        "--single-step",
        type=str,
        default=None,
        help="Only executes a single step in a workflow. The input object must "
        "match that step's inputs. Can be combined with --print-subgraph.",
    )
    subgroup.add_argument(
        "--single-process",
        type=str,
        default=None,
        help="Only executes the underlying Process (CommandLineTool, "
        "ExpressionTool, or sub-Workflow) for the given step in a workflow. "
        "This will not include any step-level processing: 'scatter', 'when'; "
        "and there will be no processing of step-level 'default', or 'valueFrom' "
        "input modifiers. However, requirements/hints from the step or parent "
        "workflow(s) will be inherited as usual."
        "The input object must match that Process's inputs.",
    )

    parser.add_argument(
        "--mpi-config-file",
        type=str,
        default=None,
        help="Platform specific configuration for MPI (parallel launcher, its "
        "flag etc). See README section 'Running MPI-based tools' for details "
        "of the format.",
    )

    parser.add_argument(
        "workflow",
        type=str,
        nargs="?",
        default=None,
        metavar="cwl_document",
        help="path or URL to a CWL Workflow, "
        "CommandLineTool, or ExpressionTool. If the `inputs_object` has a "
        "`cwl:tool` field indicating the path or URL to the cwl_document, "
        " then the `cwl_document` argument is optional.",
    )
    parser.add_argument(
        "job_order",
        nargs=argparse.REMAINDER,
        metavar="inputs_object",
        help="path or URL to a YAML or JSON "
        "formatted description of the required input values for the given "
        "`cwl_document`.",
    )

    return parser


def get_default_args() -> Dict[str, Any]:
    """Get default values of cwltool's command line options."""
    ap = arg_parser()
    args = ap.parse_args([])
    return vars(args)


class FSAction(argparse.Action):
    """Base action for our custom actions."""

    objclass: Optional[str] = None

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        nargs: Any = None,
        urljoin: Callable[[str, str], str] = urllib.parse.urljoin,
        base_uri: str = "",
        **kwargs: Any,
    ) -> None:
        """Fail if nargs is used."""
        if nargs is not None:
            raise ValueError("nargs not allowed")
        self.urljoin = urljoin
        self.base_uri = base_uri
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        setattr(
            namespace,
            self.dest,
            {
                "class": self.objclass,
                "location": self.urljoin(self.base_uri, cast(str, values)),
            },
        )


class FSAppendAction(argparse.Action):
    """Appending version of the base action for our custom actions."""

    objclass: Optional[str] = None

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        nargs: Any = None,
        urljoin: Callable[[str, str], str] = urllib.parse.urljoin,
        base_uri: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize."""
        if nargs is not None:
            raise ValueError("nargs not allowed")
        self.urljoin = urljoin
        self.base_uri = base_uri
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        g = getattr(namespace, self.dest)
        if not g:
            g = []
            setattr(namespace, self.dest, g)
        g.append(
            {
                "class": self.objclass,
                "location": self.urljoin(self.base_uri, cast(str, values)),
            }
        )


class FileAction(FSAction):
    objclass: Optional[str] = "File"


class DirectoryAction(FSAction):
    objclass: Optional[str] = "Directory"


class FileAppendAction(FSAppendAction):
    objclass: Optional[str] = "File"


class DirectoryAppendAction(FSAppendAction):
    objclass: Optional[str] = "Directory"


class AppendAction(argparse.Action):
    """An argparse action that clears the default values if any value is provided."""

    _called: bool
    """Initially set to ``False``, changed if any value is appended."""

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        nargs: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize."""
        super().__init__(option_strings, dest, **kwargs)
        self._called = False

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        g = getattr(namespace, self.dest, None)
        if g is None:
            g = []
        if self.default is not None and not self._called:
            # If any value was specified, we then clear the list of options before appending.
            # We cannot always clear the ``default`` attribute since it collects the ``values`` appended.
            self.default.clear()
            self._called = True
        g.append(values)
        setattr(namespace, self.dest, g)


def add_argument(
    toolparser: argparse.ArgumentParser,
    name: str,
    inptype: Any,
    records: List[str],
    description: str = "",
    default: Any = None,
    input_required: bool = True,
    urljoin: Callable[[str, str], str] = urllib.parse.urljoin,
    base_uri: str = "",
) -> None:
    if len(name) == 1:
        flag = "-"
    else:
        flag = "--"

    # if input_required is false, don't make the command line
    # parameter required.
    required = default is None and input_required
    if isinstance(inptype, MutableSequence):
        if len(inptype) == 1:
            inptype = inptype[0]
        elif len(inptype) == 2 and inptype[0] == "null":
            required = False
            inptype = inptype[1]
        elif len(inptype) == 2 and inptype[1] == "null":
            required = False
            inptype = inptype[0]
        else:
            _logger.debug("Can't make command line argument from %s", inptype)
            return None

    ahelp = description.replace("%", "%%")
    action: Optional[Union[Type[argparse.Action], str]] = None
    atype: Optional[Any] = None
    typekw: Dict[str, Any] = {}

    if inptype == "File":
        action = FileAction
    elif inptype == "Directory":
        action = DirectoryAction
    elif isinstance(inptype, MutableMapping) and inptype["type"] == "array":
        if inptype["items"] == "File":
            action = FileAppendAction
        elif inptype["items"] == "Directory":
            action = DirectoryAppendAction
        else:
            action = AppendAction
    elif isinstance(inptype, MutableMapping) and inptype["type"] == "enum":
        atype = str
    elif isinstance(inptype, MutableMapping) and inptype["type"] == "record":
        records.append(name)
        for field in inptype["fields"]:
            fieldname = name + "." + shortname(field["name"])
            fieldtype = field["type"]
            fielddescription = field.get("doc", "")
            add_argument(
                toolparser,
                fieldname,
                fieldtype,
                records,
                fielddescription,
                default=default.get(shortname(field["name"]), None) if default else None,
                input_required=required,
            )
        return
    elif inptype == "string":
        atype = str
    elif inptype == "int":
        atype = int
    elif inptype == "long":
        atype = int
    elif inptype == "double":
        atype = float
    elif inptype == "float":
        atype = float
    elif inptype == "boolean":
        action = "store_true"
    else:
        _logger.debug("Can't make command line argument from %s", inptype)
        return None

    if action in (FileAction, DirectoryAction, FileAppendAction, DirectoryAppendAction):
        typekw["urljoin"] = urljoin
        typekw["base_uri"] = base_uri

    if inptype != "boolean":
        typekw["type"] = atype

    toolparser.add_argument(
        flag + name,
        required=required,
        help=ahelp,
        action=action,  # type: ignore
        default=default,
        **typekw,
    )


def generate_parser(
    toolparser: argparse.ArgumentParser,
    tool: Process,
    namemap: Dict[str, str],
    records: List[str],
    input_required: bool = True,
    urljoin: Callable[[str, str], str] = urllib.parse.urljoin,
    base_uri: str = "",
) -> argparse.ArgumentParser:
    """Generate an ArgumentParser for the given CWL Process."""
    toolparser.description = tool.tool.get("doc", tool.tool.get("label", None))
    toolparser.add_argument("job_order", nargs="?", help="Job input json file")
    namemap["job_order"] = "job_order"

    for inp in tool.tool["inputs"]:
        name = shortname(inp["id"])
        namemap[name.replace("-", "_")] = name
        inptype = inp["type"]
        description = inp.get("doc", inp.get("label", ""))
        default = inp.get("default", None)
        add_argument(
            toolparser,
            name,
            inptype,
            records,
            description,
            default,
            input_required,
            urljoin,
            base_uri,
        )

    return toolparser
