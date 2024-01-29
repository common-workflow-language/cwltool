"""Shared context objects that replace use of kwargs."""

import copy
import os
import shutil
import tempfile
import threading
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    TextIO,
    Tuple,
    Union,
)

from ruamel.yaml.comments import CommentedMap
from schema_salad.avro.schema import Names
from schema_salad.ref_resolver import Loader
from schema_salad.utils import FetcherCallableType

from .mpi import MpiConfig
from .pathmapper import PathMapper
from .stdfsaccess import StdFsAccess
from .utils import DEFAULT_TMP_PREFIX, CWLObjectType, HasReqsHints, ResolverType

if TYPE_CHECKING:
    from cwl_utils.parser.cwl_v1_2 import LoadingOptions

    from .builder import Builder
    from .cwlprov.provenance_profile import ProvenanceProfile
    from .cwlprov.ro import ResearchObject
    from .mutation import MutationManager
    from .process import Process
    from .secrets import SecretStore
    from .software_requirements import DependenciesConfiguration


class ContextBase:
    """Shared kwargs based initializer for :py:class:`RuntimeContext` and :py:class:`LoadingContext`."""

    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
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
    stdout_path: Optional[str],
    stderr_path: Optional[str],
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
    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the LoadingContext from the kwargs."""
        self.debug: bool = False
        self.metadata: CWLObjectType = {}
        self.requirements: Optional[List[CWLObjectType]] = None
        self.hints: Optional[List[CWLObjectType]] = None
        self.overrides_list: List[CWLObjectType] = []
        self.loader: Optional[Loader] = None
        self.avsc_names: Optional[Names] = None
        self.disable_js_validation: bool = False
        self.js_hint_options_file: Optional[str] = None
        self.do_validate: bool = True
        self.enable_dev: bool = False
        self.strict: bool = True
        self.resolver: Optional[ResolverType] = None
        self.fetcher_constructor: Optional[FetcherCallableType] = None
        self.construct_tool_object = default_make_tool
        self.research_obj: Optional[ResearchObject] = None
        self.orcid: str = ""
        self.cwl_full_name: str = ""
        self.host_provenance: bool = False
        self.user_provenance: bool = False
        self.prov_obj: Optional["ProvenanceProfile"] = None
        self.do_update: Optional[bool] = None
        self.jobdefaults: Optional[CommentedMap] = None
        self.doc_cache: bool = True
        self.relax_path_checks: bool = False
        self.singularity: bool = False
        self.podman: bool = False
        self.eval_timeout: float = 60
        self.codegen_idx: Dict[str, Tuple[Any, "LoadingOptions"]] = {}
        self.fast_parser = False
        self.skip_resolve_all = False
        self.skip_schemas = False

        super().__init__(kwargs)

    def copy(self) -> "LoadingContext":
        """Return a copy of this :py:class:`LoadingContext`."""
        return copy.copy(self)


class RuntimeContext(ContextBase):
    outdir: Optional[str] = None
    tmpdir: str = ""
    tmpdir_prefix: str = DEFAULT_TMP_PREFIX
    tmp_outdir_prefix: str = ""
    stagedir: str = ""

    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the RuntimeContext from the kwargs."""
        select_resources_callable = Callable[
            [Dict[str, Union[int, float]], RuntimeContext],
            Dict[str, Union[int, float]],
        ]
        self.user_space_docker_cmd: Optional[str] = None
        self.secret_store: Optional["SecretStore"] = None
        self.no_read_only: bool = False
        self.custom_net: Optional[str] = None
        self.no_match_user: bool = False
        self.preserve_environment: Optional[Iterable[str]] = None
        self.preserve_entire_environment: bool = False
        self.use_container: bool = True
        self.force_docker_pull: bool = False

        self.rm_tmpdir: bool = True
        self.pull_image: bool = True
        self.rm_container: bool = True
        self.move_outputs: Union[Literal["move"], Literal["leave"], Literal["copy"]] = "move"
        self.log_dir: str = ""
        self.set_log_dir = set_log_dir
        self.log_dir_handler = log_handler
        self.streaming_allowed: bool = False

        self.singularity: bool = False
        self.podman: bool = False
        self.debug: bool = False
        self.compute_checksum: bool = True
        self.name: str = ""
        self.default_container: Optional[str] = ""
        self.find_default_container: Optional[Callable[[HasReqsHints], Optional[str]]] = None
        self.cachedir: Optional[str] = None
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
        self.job_script_provider: Optional[DependenciesConfiguration] = None
        self.select_resources: Optional[select_resources_callable] = None
        self.eval_timeout: float = 60
        self.postScatterEval: Optional[Callable[[CWLObjectType], Optional[CWLObjectType]]] = None
        self.on_error: Union[Literal["stop"], Literal["continue"]] = "stop"
        self.strict_memory_limit: bool = False
        self.strict_cpu_limit: bool = False
        self.cidfile_dir: Optional[str] = None
        self.cidfile_prefix: Optional[str] = None

        self.workflow_eval_lock: Optional[threading.Condition] = None
        self.research_obj: Optional[ResearchObject] = None
        self.orcid: str = ""
        self.cwl_full_name: str = ""
        self.process_run_id: Optional[str] = None
        self.prov_obj: Optional[ProvenanceProfile] = None
        self.mpi_config: MpiConfig = MpiConfig()
        self.default_stdout: Optional[Union[IO[bytes], TextIO]] = None
        self.default_stderr: Optional[Union[IO[bytes], TextIO]] = None
        self.validate_only: bool = False
        self.validate_stdout: Optional[Union[IO[bytes], TextIO, IO[str]]] = None
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
