import copy
from .stdfsaccess import StdFsAccess

class ContextBase(object):
    def __init__(self, kwargs):
        if kwargs:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def copy(self):
        return copy.copy(self)

class LoadingContext(ContextBase):
    default_make_tool = None

    def __init__(self, kwargs=None):
        self.debug = None
        self.metadata = None
        self.requirements = None
        self.hints = None
        self.overrides = None
        self.loader = None
        self.avsc_names = None
        self.disable_js_validation = None
        self.js_hint_options_file = None
        self.do_validate = None
        self.enable_dev = None
        self.strict = None
        self.resolver = None
        self.fetcher_constructor = None
        self.construct_tool_object = LoadingContext.default_make_tool

        super(LoadingContext, self).__init__(kwargs)

class RuntimeContext(ContextBase):
    def __init__(self, kwargs=None):
        self.user_space_docker_cmd = None
        self.secret_store = None
        self.no_read_only = None
        self.custom_net = None
        self.no_match_user = None
        self.preserve_environment = None
        self.preserve_entire_environment = None
        self.user_space_docker_cmd = None
        self.use_container = None
        self.force_docker_pull = None

        self.tmp_outdir_prefix = None
        self.tmpdir_prefix = None
        self.tmpdir = None
        self.rm_tmpdir = None
        self.pull_image = None
        self.rm_container = None
        self.move_outputs = None

        self.singularity = None
        self.disable_net = None
        self.debug = None
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
        self.builder = None
        self.docker_outdir = None
        self.docker_tmpdir = None
        self.docker_stagedir = None
        self.js_console = None
        self.job_script_provider = None
        self.select_resources = None
        self.eval_timeout = None
        self.postScatterEval = None
        self.on_error = None

        self.record_container_id = None
        self.cidfile_dir = None
        self.cidfile_prefix = None

        super(RuntimeContext, self).__init__(kwargs)

def getdefault(val, default):
    if val is None:
        return default
    else:
        return val
