import copy
from .stdfsaccess import StdFsAccess
from typing import (Any, Callable, Dict,  # pylint: disable=unused-import
                    Generator, Iterable, List, Optional, Text, Union)
from schema_salad.ref_resolver import (  # pylint: disable=unused-import
    ContextType, Fetcher, Loader)
import schema_salad.schema as schema

class ContextBase(object):
    def __init__(self, kwargs=None):
        # type: (Optional[Dict[Text, Any]]) -> None
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)


class LoadingContext(ContextBase):
    default_make_tool = None

    def __init__(self, kwargs=None):
        # type: (Optional[Dict[Text, Any]]) -> None
        self.debug = False                  # type: bool
        self.metadata = {}                  # type: Dict[Text, Any]
        self.requirements = None
        self.hints = None
        self.overrides = None
        self.loader = None                 # type: Optional[Loader]
        self.avsc_names = None             # type: Optional[schema.Names]
        self.disable_js_validation = None
        self.js_hint_options_file = None
        self.do_validate = None
        self.enable_dev = False            # type: bool
        self.strict = True                 # type: bool
        self.resolver = None
        self.fetcher_constructor = None
        self.construct_tool_object = LoadingContext.default_make_tool

        super(LoadingContext, self).__init__(kwargs)

    def copy(self):
        # type: () -> LoadingContext
        return copy.copy(self)

class RuntimeContext(ContextBase):
    def __init__(self, kwargs=None):
        # type: (Optional[Dict[Text, Any]]) -> None
        self.user_space_docker_cmd = None
        self.secret_store = None
        self.no_read_only = None
        self.custom_net = None
        self.no_match_user = None
        self.preserve_environment = None
        self.preserve_entire_environment = None
        self.user_space_docker_cmd = None
        self.use_container = None
        self.force_docker_pull = False  # type: bool

        self.tmp_outdir_prefix = None
        self.tmpdir_prefix = None
        self.tmpdir = None
        self.rm_tmpdir = None
        self.pull_image = None
        self.rm_container = None
        self.move_outputs = None

        self.singularity = None
        self.disable_net = None
        self.debug = False  # type: bool
        self.compute_checksum = None
        self.name = None
        self.default_container = None
        self.find_default_container = None
        self.cachedir = None
        self.outdir = None
        self.stagedir = None
        self.part_of = None
        self.separateDirs = None
        self.basedir = None
        self.toplevel = None
        self.mutation_manager = None
        self.make_fs_access = StdFsAccess
        self.builder = None  # type: Builder
        self.docker_outdir = None
        self.docker_tmpdir = None
        self.docker_stagedir = None
        self.js_console = False  # type: bool
        self.job_script_provider = None
        self.select_resources = None
        self.eval_timeout = None
        self.postScatterEval = None  # type: Callable[[Dict[str, Any]], Dict[str, Any]]
        self.on_error = None

        self.record_container_id = None
        self.cidfile_dir = None
        self.cidfile_prefix = None

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
