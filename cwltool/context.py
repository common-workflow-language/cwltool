"""Shared context objects that replace use of kwargs."""

import copy
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Iterable
from typing import IO, TYPE_CHECKING, Any, Literal, Optional, TextIO, Union

from ruamel.yaml.comments import CommentedMap
from schema_salad.avro.schema import Names
from schema_salad.ref_resolver import Loader
from schema_salad.utils import FetcherCallableType

from .mpi import MpiConfig
from .pathmapper import PathMapper
from .stdfsaccess import StdFsAccess
from .utils import DEFAULT_TMP_PREFIX, CWLObjectType, HasReqsHints, ResolverType

if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    from cwl_utils.parser.cwl_v1_2 import LoadingOptions

    from .builder import Builder
    from .cwlprov.provenance_profile import ProvenanceProfile
    from .cwlprov.ro import ResearchObject
    from .mutation import MutationManager
    from .process import Process
    from .secrets import SecretStore
    from .software_requirements import DependenciesConfiguration
    from .workflow_job import WorkflowJobStep


class ContextBase:
    """Shared kwargs based initializer for :py:class:`RuntimeContext` and :py:class:`LoadingContext`."""

    def __init__(self, kwargs: dict[str, Any] | None = None) -> None:
        """Initialize."""
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)


def make_tool_notimpl(toolpath_object: CommentedMap, loadingContext: "LoadingContext") -> "Process":
    """Fake implementation of the make tool function."""
    raise NotImplementedError()


default_make_tool = make_tool_notimpl


def log_handler(
    outdir: str,
    base_path_logs: str,
    stdout_path: str | None,
    stderr_path: str | None,
) -> None:
    """Move logs from log location to final output."""
    if outdir != base_path_logs:
        if stdout_path:
            new_stdout_path = stdout_path.replace(base_path_logs, outdir)
            shutil.copy2(stdout_path, new_stdout_path)
        if stderr_path:
            new_stderr_path = stderr_path.replace(base_path_logs, outdir)
            shutil.copy2(stderr_path, new_stderr_path)


def set_log_dir(outdir: str, log_dir: str, subdir_name: str) -> str:
    """Set the log directory."""
    if log_dir == "":
        return outdir
    else:
        return log_dir + "/" + subdir_name


class LoadingContext(ContextBase):
    def __init__(self, kwargs: dict[str, Any] | None = None) -> None:
        """Initialize the LoadingContext from the kwargs."""
        self.debug: bool = False
        self.metadata: CWLObjectType = {}
        self.requirements: list[CWLObjectType] | None = None
        self.hints: list[CWLObjectType] | None = None
        self.overrides_list: list[CWLObjectType] = []
        self.loader: Loader | None = None
        self.avsc_names: Names | None = None
        self.disable_js_validation: bool = False
        self.js_hint_options_file: str | None = None
        self.do_validate: bool = True
        self.enable_dev: bool = False
        self.strict: bool = True
        self.resolver: ResolverType | None = None
        self.fetcher_constructor: FetcherCallableType | None = None
        self.construct_tool_object = default_make_tool
        self.research_obj: ResearchObject | None = None
        self.orcid: str = ""
        self.cwl_full_name: str = ""
        self.host_provenance: bool = False
        self.user_provenance: bool = False
        self.prov_obj: Optional["ProvenanceProfile"] = None
        self.do_update: bool | None = None
        self.jobdefaults: CommentedMap | None = None
        self.doc_cache: bool = True
        self.relax_path_checks: bool = False
        self.singularity: bool = False
        self.podman: bool = False
        self.eval_timeout: float = 60
        self.codegen_idx: dict[str, tuple[Any, "LoadingOptions"]] = {}
        self.fast_parser = False
        self.skip_resolve_all = False
        self.skip_schemas = False

        super().__init__(kwargs)

    def copy(self) -> "LoadingContext":
        """Return a copy of this :py:class:`LoadingContext`."""
        return copy.copy(self)


class RuntimeContext(ContextBase):
    outdir: str | None = None
    tmpdir: str = ""
    tmpdir_prefix: str = DEFAULT_TMP_PREFIX
    tmp_outdir_prefix: str = ""
    stagedir: str = ""

    def __init__(self, kwargs: dict[str, Any] | None = None) -> None:
        """Initialize the RuntimeContext from the kwargs."""
        select_resources_callable = Callable[
            [dict[str, Union[int, float]], RuntimeContext],
            dict[str, Union[int, float]],
        ]
        self.user_space_docker_cmd: str | None = None
        self.secret_store: Optional["SecretStore"] = None
        self.no_read_only: bool = False
        self.custom_net: str | None = None
        self.no_match_user: bool = False
        self.preserve_environment: Iterable[str] | None = None
        self.preserve_entire_environment: bool = False
        self.use_container: bool = True
        self.force_docker_pull: bool = False

        self.rm_tmpdir: bool = True
        self.pull_image: bool = True
        self.rm_container: bool = True
        self.move_outputs: Literal["move"] | Literal["leave"] | Literal["copy"] = "move"
        self.log_dir: str = ""
        self.set_log_dir = set_log_dir
        self.log_dir_handler = log_handler
        self.streaming_allowed: bool = False

        self.singularity: bool = False
        self.image_base_path: str | None = None
        self.podman: bool = False
        self.debug: bool = False
        self.compute_checksum: bool = True
        self.name: str = ""
        self.default_container: str | None = ""
        self.find_default_container: Callable[[HasReqsHints], str | None] | None = None
        self.cachedir: str | None = None
        self.part_of: str = ""
        self.basedir: str = ""
        self.toplevel: bool = False
        self.mutation_manager: Optional["MutationManager"] = None
        self.make_fs_access = StdFsAccess
        self.path_mapper = PathMapper
        self.builder: Optional["Builder"] = None
        self.docker_outdir: str = ""
        self.docker_tmpdir: str = ""
        self.docker_stagedir: str = ""
        self.js_console: bool = False
        self.job_script_provider: DependenciesConfiguration | None = None
        self.select_resources: select_resources_callable | None = None
        self.eval_timeout: float = 60
        self.postScatterEval: Callable[[CWLObjectType], CWLObjectType | None] | None = None
        self.on_error: Literal["stop"] | Literal["continue"] = "stop"
        self.strict_memory_limit: bool = False
        self.strict_cpu_limit: bool = False
        self.cidfile_dir: str | None = None
        self.cidfile_prefix: str | None = None

        self.workflow_eval_lock: Union[threading.Condition, None] = None
        self.research_obj: ResearchObject | None = None
        self.orcid: str = ""
        self.cwl_full_name: str = ""
        self.process_run_id: str | None = None
        self.prov_host: bool = False
        self.prov_user: bool = False
        self.prov_obj: ProvenanceProfile | None = None
        self.mpi_config: MpiConfig = MpiConfig()
        self.default_stdout: IO[bytes] | TextIO | None = None
        self.default_stderr: IO[bytes] | TextIO | None = None
        self.validate_only: bool = False
        self.validate_stdout: Optional["SupportsWrite[str]"] = None
        self.workflow_job_step_name_callback: None | (
            Callable[[WorkflowJobStep, CWLObjectType], str]
        ) = None

        super().__init__(kwargs)
        if self.tmp_outdir_prefix == "":
            self.tmp_outdir_prefix = self.tmpdir_prefix

    def get_outdir(self) -> str:
        """Return :py:attr:`outdir` or create one with :py:attr:`tmp_outdir_prefix`."""
        if self.outdir:
            return self.outdir
        return self.create_outdir()

    def get_tmpdir(self) -> str:
        """Return :py:attr:`tmpdir` or create one with :py:attr:`tmpdir_prefix`."""
        if self.tmpdir:
            return self.tmpdir
        return self.create_tmpdir()

    def get_stagedir(self) -> str:
        """Return :py:attr:`stagedir` or create one with :py:attr:`tmpdir_prefix`."""
        if self.stagedir:
            return self.stagedir
        tmp_dir, tmp_prefix = os.path.split(self.tmpdir_prefix)
        return tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir)

    def create_tmpdir(self) -> str:
        """Create a temporary directory that respects :py:attr:`tmpdir_prefix`."""
        tmp_dir, tmp_prefix = os.path.split(self.tmpdir_prefix)
        return tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir)

    def create_outdir(self) -> str:
        """Create a temporary directory that respects :py:attr:`tmp_outdir_prefix`."""
        out_dir, out_prefix = os.path.split(self.tmp_outdir_prefix)
        return tempfile.mkdtemp(prefix=out_prefix, dir=out_dir)

    def copy(self) -> "RuntimeContext":
        """Return a copy of this :py:class:`RuntimeContext`."""
        return copy.copy(self)


def getdefault(val: Any, default: Any) -> Any:
    """Return the ``val`` using the ``default`` as backup in case the val is ``None``."""
    if val is None:
        return default
    else:
        return val
