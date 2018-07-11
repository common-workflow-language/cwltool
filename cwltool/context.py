import copy
import threading  # pylint: disable=unused-import

from .utils import DEFAULT_TMP_PREFIX
from .stdfsaccess import StdFsAccess
from typing import (Any, Callable, Dict,  # pylint: disable=unused-import
                    Generator, Iterable, List, Optional, Text, Union, AnyStr)
from schema_salad.ref_resolver import (  # pylint: disable=unused-import
    ContextType, Fetcher, Loader)
import schema_salad.schema as schema
from .builder import Builder, HasReqsHints
from .mutation import MutationManager
from .software_requirements import DependenciesConfiguration
from .secrets import SecretStore
import six

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .process import Process
    from .provenance import (ResearchObject,  # pylint: disable=unused-import
                             CreateProvProfile)

class ContextBase(object):
    def __init__(self, kwargs=None):
        # type: (Optional[Dict[str, Any]]) -> None
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

def make_tool_notimpl(toolpath_object,      # type: Dict[Text, Any]
                      loadingContext        # type: LoadingContext
                     ):  # type: (...) -> Process
    raise NotImplementedError()

default_make_tool = make_tool_notimpl  # type: Callable[[Dict[Text, Any], LoadingContext], Process]

class LoadingContext(ContextBase):

    def __init__(self, kwargs=None):
        # type: (Optional[Dict[str, Any]]) -> None
        self.debug = False                 # type: bool
        self.metadata = {}                 # type: Dict[Text, Any]
        self.requirements = None
        self.hints = None
        self.overrides_list = []           # type: List[Dict[Text, Any]]
        self.loader = None                 # type: Optional[Loader]
        self.avsc_names = None             # type: Optional[schema.Names]
        self.disable_js_validation = False # type: bool
        self.js_hint_options_file = None
        self.do_validate = True            # type: bool
        self.enable_dev = False            # type: bool
        self.strict = True                 # type: bool
        self.resolver = None
        self.fetcher_constructor = None
        self.construct_tool_object = default_make_tool
        self.research_obj = None           # type: Optional[ResearchObject]
        self.orcid = None
        self.cwl_full_name = None
        self.host_provenance = False       # type: bool
        self.user_provenance = False       # type: bool
        self.prov_obj = None               # type: Optional[CreateProvProfile]

        super(LoadingContext, self).__init__(kwargs)

    def copy(self):
        # type: () -> LoadingContext
        return copy.copy(self)

class RuntimeContext(ContextBase):
    def __init__(self, kwargs=None):
        # type: (Optional[Dict[str, Any]]) -> None
        select_resources_callable = Callable[  # pylint: disable=unused-variable
            [Dict[str, int], RuntimeContext], Dict[str, int]]
        self.user_space_docker_cmd = "" # type: Text
        self.secret_store = None        # type: Optional[SecretStore]
        self.no_read_only = False       # type: bool
        self.custom_net = ""            # type: Text
        self.no_match_user = False      # type: bool
        self.preserve_environment = ""  # type: Optional[Iterable[str]]
        self.preserve_entire_environment = False  # type: bool
        self.use_container = True       # type: bool
        self.force_docker_pull = False  # type: bool

        self.tmp_outdir_prefix = DEFAULT_TMP_PREFIX  # type: Text
        self.tmpdir_prefix = DEFAULT_TMP_PREFIX  # type: Text
        self.tmpdir = ""                # type: Text
        self.rm_tmpdir = True           # type: bool
        self.pull_image = True          # type: bool
        self.rm_container = True        # type: bool
        self.move_outputs = ""          # type: Text

        self.singularity = False        # type: bool
        self.disable_net = None
        self.debug = False              # type: bool
        self.compute_checksum = True    # type: bool
        self.name = ""                  # type: Text
        self.default_container = ""     # type: Text
        self.find_default_container = None  # type: Optional[Callable[[HasReqsHints], Optional[Text]]]
        self.cachedir = None            # type: Optional[Text]
        self.outdir = None              # type: Optional[Text]
        self.stagedir = ""              # type: Text
        self.part_of = ""               # type: Text
        self.basedir = ""               # type: Text
        self.toplevel = False           # type: bool
        self.mutation_manager = None    # type: Optional[MutationManager]
        self.make_fs_access = StdFsAccess  # type: Callable[[Text], StdFsAccess]
        self.builder = None             # type: Optional[Builder]
        self.docker_outdir = ""         # type: Text
        self.docker_tmpdir = ""         # type: Text
        self.docker_stagedir = ""       # type: Text
        self.js_console = False         # type: bool
        self.job_script_provider = None  # type: Optional[DependenciesConfiguration]
        self.select_resources = None    # type: Optional[select_resources_callable]
        self.eval_timeout = 20          # type: float
        self.postScatterEval = None     # type: Optional[Callable[[Dict[Text, Any]], Dict[Text, Any]]]
        self.on_error = "stop"          # type: Text

        self.record_container_id = None
        self.cidfile_dir = None
        self.cidfile_prefix = None

        self.workflow_eval_lock = None  # type: Optional[threading.Condition]
        self.research_obj = None        # type: Optional[ResearchObject]
        self.orcid = None
        self.cwl_full_name = None
        self.process_run_id = None      # type: Optional[str]
        self.prov_obj = None            # type: Optional[CreateProvProfile]
        self.reference_locations = {}   # type: Dict[Text, Text]
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
