"""Shared context objects that replace use of kwargs."""
import copy
import threading
from typing import Any, Callable, Dict, Iterable, List, MutableMapping, Optional

from typing_extensions import TYPE_CHECKING

# move to a regular typing import when Python 3.3-3.6 is no longer supported
from ruamel.yaml.comments import CommentedMap
from schema_salad import schema
from schema_salad.ref_resolver import Loader

from .builder import Builder, HasReqsHints
from .mutation import MutationManager
from .pathmapper import PathMapper
from .secrets import SecretStore
from .software_requirements import DependenciesConfiguration
from .stdfsaccess import StdFsAccess
from .utils import DEFAULT_TMP_PREFIX

if TYPE_CHECKING:
    from .process import Process
    from .provenance import (
        ResearchObject,  # pylint: disable=unused-import
        ProvenanceProfile,
    )


class ContextBase(object):
    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Initialize."""
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)


def make_tool_notimpl(
    toolpath_object,  # type: MutableMapping[str, Any]
    loadingContext,  # type: LoadingContext
):  # type: (...) -> Process
    raise NotImplementedError()


default_make_tool = make_tool_notimpl


class LoadingContext(ContextBase):
    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the LoadingContext from the kwargs."""
        self.debug = False  # type: bool
        self.metadata = {}  # type: Dict[str, Any]
        self.requirements = None  # type: Optional[List[Dict[str, Any]]]
        self.hints = None  # type: Optional[List[Dict[str, Any]]]
        self.overrides_list = []  # type: List[Dict[str, Any]]
        self.loader = None  # type: Optional[Loader]
        self.avsc_names = None  # type: Optional[schema.Names]
        self.disable_js_validation = False  # type: bool
        self.js_hint_options_file = None
        self.do_validate = True  # type: bool
        self.enable_dev = False  # type: bool
        self.strict = True  # type: bool
        self.resolver = None
        self.fetcher_constructor = None
        self.construct_tool_object = default_make_tool
        self.research_obj = None  # type: Optional[ResearchObject]
        self.orcid = ""  # type: str
        self.cwl_full_name = ""  # type: str
        self.host_provenance = False  # type: bool
        self.user_provenance = False  # type: bool
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.do_update = None  # type: Optional[bool]
        self.jobdefaults = None  # type: Optional[CommentedMap]

        super(LoadingContext, self).__init__(kwargs)

    def copy(self):
        # type: () -> LoadingContext
        return copy.copy(self)


class RuntimeContext(ContextBase):
    def __init__(self, kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Initializet the RuntimeContext from the kwargs."""
        select_resources_callable = Callable[  # pylint: disable=unused-variable
            [Dict[str, int], RuntimeContext], Dict[str, int]
        ]
        self.user_space_docker_cmd = ""  # type: str
        self.secret_store = None  # type: Optional[SecretStore]
        self.no_read_only = False  # type: bool
        self.custom_net = ""  # type: str
        self.no_match_user = False  # type: bool
        self.preserve_environment = ""  # type: Optional[Iterable[str]]
        self.preserve_entire_environment = False  # type: bool
        self.use_container = True  # type: bool
        self.force_docker_pull = False  # type: bool

        self.tmp_outdir_prefix = DEFAULT_TMP_PREFIX  # type: str
        self.tmpdir_prefix = DEFAULT_TMP_PREFIX  # type: str
        self.tmpdir = ""  # type: str
        self.rm_tmpdir = True  # type: bool
        self.pull_image = True  # type: bool
        self.rm_container = True  # type: bool
        self.move_outputs = "move"  # type: str

        self.singularity = False  # type: bool
        self.disable_net = False  # type: bool
        self.debug = False  # type: bool
        self.compute_checksum = True  # type: bool
        self.name = ""  # type: str
        self.default_container = ""  # type: str
        self.find_default_container = (
            None
        )  # type: Optional[Callable[[HasReqsHints], Optional[str]]]
        self.cachedir = None  # type: Optional[str]
        self.outdir = None  # type: Optional[str]
        self.stagedir = ""  # type: str
        self.part_of = ""  # type: str
        self.basedir = ""  # type: str
        self.toplevel = False  # type: bool
        self.mutation_manager = None  # type: Optional[MutationManager]
        self.make_fs_access = StdFsAccess  # type: Callable[[str], StdFsAccess]
        self.path_mapper = PathMapper
        self.builder = None  # type: Optional[Builder]
        self.docker_outdir = ""  # type: str
        self.docker_tmpdir = ""  # type: str
        self.docker_stagedir = ""  # type: str
        self.js_console = False  # type: bool
        self.job_script_provider = None  # type: Optional[DependenciesConfiguration]
        self.select_resources = None  # type: Optional[select_resources_callable]
        self.eval_timeout = 20  # type: float
        self.postScatterEval = (
            None
        )  # type: Optional[Callable[[MutableMapping[str, Any]], Dict[str, Any]]]
        self.on_error = "stop"  # type: str
        self.strict_memory_limit = False  # type: bool

        self.cidfile_dir = None
        self.cidfile_prefix = None

        self.workflow_eval_lock = None  # type: Optional[threading.Condition]
        self.research_obj = None  # type: Optional[ResearchObject]
        self.orcid = ""  # type: str
        self.cwl_full_name = ""  # type: str
        self.process_run_id = None  # type: Optional[str]
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        super(RuntimeContext, self).__init__(kwargs)

    def copy(self):
        # type: () -> RuntimeContext
        return copy.copy(self)


def getdefault(val, default):
    # type: (Any, Any) -> Any
    if val is None:
        return default
    else:
        return val
