"""Implementation of CommandLineTool."""
from __future__ import absolute_import

import copy
import hashlib
import json
import locale
import logging
import os
import re
import shutil
import tempfile
import threading
from functools import cmp_to_key, partial
from typing import (Any, Callable, Dict, Generator, List, MutableMapping,
                    MutableSequence, Optional, Set, Union, cast)

import shellescape
from schema_salad import validate
from schema_salad.ref_resolver import file_uri, uri_file_path
from schema_salad.sourceline import SourceLine
from six import string_types

from six.moves import map, urllib
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text, Type)
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .builder import (CONTENT_LIMIT, Builder,  # pylint: disable=unused-import
                      substitute)
from .context import LoadingContext  # pylint: disable=unused-import
from .context import RuntimeContext, getdefault
from .docker import DockerCommandLineJob
from .errors import WorkflowException
from .flatten import flatten
from .job import CommandLineJob, JobBase  # pylint: disable=unused-import
from .loghandler import _logger
from .mutation import MutationManager  # pylint: disable=unused-import
from .pathmapper import (PathMapper, adjustDirObjs, adjustFileObjs,
                         get_listing, trim_listing, visit_class)
from .process import (Process, UnsupportedRequirement,
                      _logger_validation_warnings, compute_checksums,
                      normalizeFilesDirs, shortname, uniquename)
from .singularity import SingularityCommandLineJob
from .software_requirements import (  # pylint: disable=unused-import
    DependenciesConfiguration)
from .stdfsaccess import StdFsAccess  # pylint: disable=unused-import
from .utils import (aslist, convert_pathsep_to_unix,
                    docker_windows_path_adjust, json_dumps, onWindows,
                    random_outdir, windows_default_container_id)
if TYPE_CHECKING:
    from .provenance import CreateProvProfile  # pylint: disable=unused-import

ACCEPTLIST_EN_STRICT_RE = re.compile(r"^[a-zA-Z0-9._+-]+$")
ACCEPTLIST_EN_RELAXED_RE = re.compile(r".*")  # Accept anything
ACCEPTLIST_RE = ACCEPTLIST_EN_STRICT_RE
DEFAULT_CONTAINER_MSG = """
We are on Microsoft Windows and not all components of this CWL description have a
container specified. This means that these steps will be executed in the default container,
which is %s.

Note, this could affect portability if this CWL description relies on non-POSIX features
or commands in this container. For best results add the following to your CWL
description's hints section:

hints:
  DockerRequirement:
    dockerPull: %s
"""


class ExpressionTool(Process):
    class ExpressionJob(object):

        def __init__(self,
                     builder,          # type: Builder
                     script,           # type: Dict[Text, Text]
                     output_callback,  # type: Callable[[Any, Any], Any]
                     requirements,     # type: Dict[Text, Text]
                     hints,            # type: Dict[Text, Text]
                     outdir=None,      # type: Optional[Text]
                     tmpdir=None,      # type: Optional[Text]
                    ):  # type: (...) -> None
            self.builder = builder
            self.requirements = requirements
            self.hints = hints
            self.collect_outputs = None  # type: Optional[Callable[[Any], Any]]
            self.output_callback = output_callback
            self.outdir = outdir
            self.tmpdir = tmpdir
            self.script = script
            self.prov_obj = None  # type: Optional[CreateProvProfile]

        def run(self, runtimeContext):  # type: (RuntimeContext) -> None
            try:
                ev = self.builder.do_eval(self.script)
                normalizeFilesDirs(ev)
                self.output_callback(ev, "success")
            except Exception as err:
                _logger.warning(u"Failed to evaluate expression:\n%s",
                                err, exc_info=runtimeContext.debug)
                self.output_callback({}, "permanentFail")

    def job(self,
            job_order,         # type: MutableMapping[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            runtimeContext     # type: RuntimeContext
           ):
        # type: (...) -> Generator[ExpressionTool.ExpressionJob, None, None]
        builder = self._init_job(job_order, runtimeContext)

        job = ExpressionTool.ExpressionJob(
            builder, self.tool["expression"], output_callbacks,
            self.requirements, self.hints)
        job.prov_obj = runtimeContext.prov_obj
        yield job


def remove_path(f):  # type: (Dict[Text, Any]) -> None
    if "path" in f:
        del f["path"]


def revmap_file(builder, outdir, f):
    # type: (Builder, Text, Dict[Text, Any]) -> Union[Dict[Text, Any], None]

    """Remap a file from internal path to external path.

    For Docker, this maps from the path inside tho container to the path
    outside the container. Recognizes files in the pathmapper or remaps
    internal output directories to the external directory.
    """

    split = urllib.parse.urlsplit(outdir)
    if not split.scheme:
        outdir = file_uri(str(outdir))

    # builder.outdir is the inner (container/compute node) output directory
    # outdir is the outer (host/storage system) output directory

    if "location" in f and "path" not in f:
        if f["location"].startswith("file://"):
            f["path"] = convert_pathsep_to_unix(uri_file_path(f["location"]))
        else:
            return f

    if "path" in f:
        path = f["path"]
        uripath = file_uri(path)
        del f["path"]

        if "basename" not in f:
            f["basename"] = os.path.basename(path)

        assert builder.pathmapper is not None
        revmap_f = builder.pathmapper.reversemap(path)

        if revmap_f and not builder.pathmapper.mapper(revmap_f[0]).type.startswith("Writable"):
            f["location"] = revmap_f[1]
        elif uripath == outdir or uripath.startswith(outdir+os.sep):
            f["location"] = file_uri(path)
        elif path == builder.outdir or path.startswith(builder.outdir+os.sep):
            f["location"] = builder.fs_access.join(outdir, path[len(builder.outdir) + 1:])
        elif not os.path.isabs(path):
            f["location"] = builder.fs_access.join(outdir, path)
        else:
            raise WorkflowException(u"Output file path %s must be within designated output directory (%s) or an input "
                                    u"file pass through." % (path, builder.outdir))
        return f

    raise WorkflowException(u"Output File object is missing both 'location' "
                            "and 'path' fields: %s" % f)


class CallbackJob(object):
    def __init__(self, job, output_callback, cachebuilder, jobcache):
        # type: (CommandLineTool, Callable[[Any, Any], Any], Builder, Text) -> None
        self.job = job
        self.output_callback = output_callback
        self.cachebuilder = cachebuilder
        self.outdir = jobcache
        self.prov_obj = None  # type: Optional[CreateProvProfile]

    def run(self, runtimeContext):
        # type: (RuntimeContext) -> None
        self.output_callback(self.job.collect_output_ports(
            self.job.tool["outputs"],
            self.cachebuilder,
            self.outdir,
            getdefault(runtimeContext.compute_checksum, True)), "success")


def check_adjust(builder, file_o):
    # type: (Builder, Dict[Text, Any]) -> Dict[Text, Any]
    """
    Map files to assigned path inside a container.

    We need to also explicitly walk over input, as implicit reassignment
    doesn't reach everything in builder.bindings
    """

    assert builder.pathmapper is not None
    file_o["path"] = docker_windows_path_adjust(
        builder.pathmapper.mapper(file_o["location"])[1])
    file_o["dirname"], file_o["basename"] = os.path.split(file_o["path"])
    if file_o["class"] == "File":
        file_o["nameroot"], file_o["nameext"] = os.path.splitext(
            file_o["basename"])
    if not ACCEPTLIST_RE.match(file_o["basename"]):
        raise WorkflowException(
            "Invalid filename: '{}' contains illegal characters".format(
                file_o["basename"]))
    return file_o

def check_valid_locations(fs_access, ob):
    if ob["location"].startswith("_:"):
        pass
    if ob["class"] == "File" and not fs_access.isfile(ob["location"]):
        raise validate.ValidationException("Does not exist or is not a File: '%s'" % ob["location"])
    if ob["class"] == "Directory" and not fs_access.isdir(ob["location"]):
        raise validate.ValidationException("Does not exist or is not a Directory: '%s'" % ob["location"])


OutputPorts = Dict[Text, Union[None, Text, List[Union[Dict[Text, Any], Text]], Dict[Text, Any]]]

class CommandLineTool(Process):
    def __init__(self, toolpath_object, loadingContext):
        # type: (MutableMapping[Text, Any], LoadingContext) -> None
        super(CommandLineTool, self).__init__(toolpath_object, loadingContext)
        self.prov_obj = loadingContext.prov_obj

    def make_job_runner(self,
                        runtimeContext       # type: RuntimeContext
                       ):  # type: (...) -> Type[JobBase]
        dockerReq, _ = self.get_requirement("DockerRequirement")
        if not dockerReq and runtimeContext.use_container:
            if runtimeContext.find_default_container:
                default_container = runtimeContext.find_default_container(self)
                if default_container:
                    self.requirements.insert(0, {
                        "class": "DockerRequirement",
                        "dockerPull": default_container
                    })
                    dockerReq = self.requirements[0]
                    if default_container == windows_default_container_id \
                            and runtimeContext.use_container and onWindows():
                        _logger.warning(
                            DEFAULT_CONTAINER_MSG, windows_default_container_id,
                            windows_default_container_id)

        if dockerReq and runtimeContext.use_container:
            if runtimeContext.singularity:
                return SingularityCommandLineJob
            return DockerCommandLineJob
        for t in reversed(self.requirements):
            if t["class"] == "DockerRequirement":
                raise UnsupportedRequirement(
                    "--no-container, but this CommandLineTool has "
                    "DockerRequirement under 'requirements'.")
        return CommandLineJob

    def make_path_mapper(self, reffiles, stagedir, runtimeContext, separateDirs):
        # type: (List[Any], Text, RuntimeContext, bool) -> PathMapper
        return PathMapper(reffiles, runtimeContext.basedir, stagedir, separateDirs)

    def updatePathmap(self, outdir, pathmap, fn):
        # type: (Text, PathMapper, Dict) -> None
        if "location" in fn and fn["location"] in pathmap:
            pathmap.update(fn["location"], pathmap.mapper(fn["location"]).resolved,
                           os.path.join(outdir, fn["basename"]),
                           ("Writable" if fn.get("writable") else "") + fn["class"], False)
        for sf in fn.get("secondaryFiles", []):
            self.updatePathmap(outdir, pathmap, sf)
        for ls in fn.get("listing", []):
            self.updatePathmap(os.path.join(outdir, fn["basename"]), pathmap, ls)

    def job(self,
            job_order,         # type: MutableMapping[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            runtimeContext     # RuntimeContext
           ):
        # type: (...) -> Generator[Union[JobBase, CallbackJob], None, None]

        require_prefix = ""
        if self.metadata["cwlVersion"] == "v1.0":
            require_prefix = "http://commonwl.org/cwltool#"

        workReuse = self.get_requirement(require_prefix+"WorkReuse")[0]
        enableReuse = workReuse.get("enableReuse", True) if workReuse else True

        jobname = uniquename(runtimeContext.name or shortname(self.tool.get("id", "job")))
        if runtimeContext.cachedir and enableReuse:
            cachecontext = runtimeContext.copy()
            cachecontext.outdir = "/out"
            cachecontext.tmpdir = "/tmp"
            cachecontext.stagedir = "/stage"
            cachebuilder = self._init_job(job_order, cachecontext)
            cachebuilder.pathmapper = PathMapper(cachebuilder.files,
                                                 runtimeContext.basedir,
                                                 cachebuilder.stagedir,
                                                 separateDirs=False)
            _check_adjust = partial(check_adjust, cachebuilder)
            visit_class([cachebuilder.files, cachebuilder.bindings],
                        ("File", "Directory"), _check_adjust)

            cmdline = flatten(list(map(cachebuilder.generate_arg, cachebuilder.bindings)))
            (docker_req, _) = self.get_requirement("DockerRequirement")
            if docker_req and runtimeContext.use_container:
                dockerimg = docker_req.get("dockerImageId") or docker_req.get("dockerPull")
            elif runtimeContext.default_container is not None and runtimeContext.use_container:
                dockerimg = runtimeContext.default_container
            else:
                dockerimg = None

            if dockerimg:
                cmdline = ["docker", "run", dockerimg] + cmdline
                # not really run using docker, just for hashing purposes
            keydict = {u"cmdline": cmdline}

            for shortcut in ["stdout", "stderr"]:  # later, add "stdin"
                if shortcut in self.tool:
                    keydict[shortcut] = self.tool[shortcut]

            for location, fobj in cachebuilder.pathmapper.items():
                if fobj.type == "File":
                    checksum = next(
                        (e['checksum'] for e in cachebuilder.files
                         if 'location' in e and e['location'] == location
                         and 'checksum' in e
                         and e['checksum'] != 'sha1$hash'), None)
                    fobj_stat = os.stat(fobj.resolved)
                    if checksum:
                        keydict[fobj.resolved] = [fobj_stat.st_size, checksum]
                    else:
                        keydict[fobj.resolved] = [fobj_stat.st_size,
                                                  int(fobj_stat.st_mtime * 1000)]

            interesting = {"DockerRequirement",
                           "EnvVarRequirement",
                           "CreateFileRequirement",
                           "ShellCommandRequirement"}
            for rh in (self.original_requirements, self.original_hints):
                for r in reversed(rh):
                    if r["class"] in interesting and r["class"] not in keydict:
                        keydict[r["class"]] = r

            keydictstr = json_dumps(keydict, separators=(',', ':'),
                                    sort_keys=True)
            cachekey = hashlib.md5(keydictstr.encode('utf-8')).hexdigest()

            _logger.debug("[job %s] keydictstr is %s -> %s", jobname,
                          keydictstr, cachekey)

            jobcache = os.path.join(runtimeContext.cachedir, cachekey)
            jobcachepending = "{}.{}.pending".format(
                jobcache, threading.current_thread().ident)

            if os.path.isdir(jobcache) and not os.path.isfile(jobcachepending):
                if docker_req and runtimeContext.use_container:
                    cachebuilder.outdir = runtimeContext.docker_outdir or random_outdir()
                else:
                    cachebuilder.outdir = jobcache

                _logger.info("[job %s] Using cached output in %s", jobname, jobcache)
                yield CallbackJob(self, output_callbacks, cachebuilder, jobcache)
                return
            else:
                _logger.info("[job %s] Output of job will be cached in %s", jobname, jobcache)
                shutil.rmtree(jobcache, True)
                os.makedirs(jobcache)
                runtimeContext = runtimeContext.copy()
                runtimeContext.outdir = jobcache
                open(jobcachepending, "w").close()

                def rm_pending_output_callback(output_callbacks, jobcachepending,
                                               outputs, processStatus):
                    if processStatus == "success":
                        os.remove(jobcachepending)
                    output_callbacks(outputs, processStatus)

                output_callbacks = partial(
                    rm_pending_output_callback, output_callbacks, jobcachepending)

        builder = self._init_job(job_order, runtimeContext)

        reffiles = copy.deepcopy(builder.files)

        j = self.make_job_runner(runtimeContext)(
            builder, builder.job, self.make_path_mapper, self.requirements,
            self.hints, jobname)
        j.prov_obj = self.prov_obj
        j.successCodes = self.tool.get("successCodes")
        j.temporaryFailCodes = self.tool.get("temporaryFailCodes")
        j.permanentFailCodes = self.tool.get("permanentFailCodes")

        debug = _logger.isEnabledFor(logging.DEBUG)

        if debug:
            _logger.debug(u"[job %s] initializing from %s%s",
                          j.name,
                          self.tool.get("id", ""),
                          u" as part of %s" % runtimeContext.part_of
                          if runtimeContext.part_of else "")
            _logger.debug(u"[job %s] %s", j.name, json_dumps(job_order,
                                                             indent=4))

        builder.pathmapper = self.make_path_mapper(
            reffiles, builder.stagedir, runtimeContext, True)
        builder.requirements = j.requirements

        _check_adjust = partial(check_adjust, builder)

        visit_class([builder.files, builder.bindings], ("File", "Directory"), _check_adjust)

        initialWorkdir = self.get_requirement("InitialWorkDirRequirement")[0]
        if initialWorkdir:
            ls = []  # type: List[Dict[Text, Any]]
            if isinstance(initialWorkdir["listing"], string_types):
                ls = builder.do_eval(initialWorkdir["listing"])
            else:
                for t in initialWorkdir["listing"]:
                    if "entry" in t:
                        et = {u"entry": builder.do_eval(t["entry"], strip_whitespace=False)}
                        if "entryname" in t:
                            et["entryname"] = builder.do_eval(t["entryname"])
                        else:
                            et["entryname"] = None
                        et["writable"] = t.get("writable", False)
                        ls.append(et)
                    else:
                        ls.append(builder.do_eval(t))
            for i, t in enumerate(ls):
                if "entry" in t:
                    if isinstance(t["entry"], string_types):
                        ls[i] = {
                            "class": "File",
                            "basename": t["entryname"],
                            "contents": t["entry"],
                            "writable": t.get("writable")
                        }
                    else:
                        if t.get("entryname") or t.get("writable"):
                            t = copy.deepcopy(t)
                            if t.get("entryname"):
                                t["entry"]["basename"] = t["entryname"]
                            t["entry"]["writable"] = t.get("writable")
                        ls[i] = t["entry"]
            j.generatefiles["listing"] = ls
            for l in ls:
                self.updatePathmap(builder.outdir, builder.pathmapper, l)
            visit_class([builder.files, builder.bindings], ("File", "Directory"), _check_adjust)

        if debug:
            _logger.debug(u"[job %s] path mappings is %s", j.name,
                          json_dumps({p: builder.pathmapper.mapper(p)
                                      for p in builder.pathmapper.files()},
                                     indent=4))

        if self.tool.get("stdin"):
            with SourceLine(self.tool, "stdin", validate.ValidationException, debug):
                j.stdin = builder.do_eval(self.tool["stdin"])
                assert j.stdin is not None
                reffiles.append({"class": "File", "path": j.stdin})

        if self.tool.get("stderr"):
            with SourceLine(self.tool, "stderr", validate.ValidationException, debug):
                j.stderr = builder.do_eval(self.tool["stderr"])
                assert j.stderr is not None
                if os.path.isabs(j.stderr) or ".." in j.stderr:
                    raise validate.ValidationException(
                        "stderr must be a relative path, got '%s'" % j.stderr)

        if self.tool.get("stdout"):
            with SourceLine(self.tool, "stdout", validate.ValidationException, debug):
                j.stdout = builder.do_eval(self.tool["stdout"])
                assert j.stdout is not None
                if os.path.isabs(j.stdout) or ".." in j.stdout or not j.stdout:
                    raise validate.ValidationException(
                        "stdout must be a relative path, got '%s'" % j.stdout)

        if debug:
            _logger.debug(u"[job %s] command line bindings is %s", j.name,
                          json_dumps(builder.bindings, indent=4))

        dockerReq = self.get_requirement("DockerRequirement")[0]
        if dockerReq and runtimeContext.use_container:
            out_prefix = getdefault(runtimeContext.tmp_outdir_prefix, 'tmp')
            j.outdir = runtimeContext.outdir or \
                tempfile.mkdtemp(prefix=out_prefix)  # type: ignore
            tmpdir_prefix = getdefault(runtimeContext.tmpdir_prefix, 'tmp')
            j.tmpdir = runtimeContext.tmpdir or \
                tempfile.mkdtemp(prefix=tmpdir_prefix)  # type: ignore
            j.stagedir = tempfile.mkdtemp(prefix=tmpdir_prefix)
        else:
            j.outdir = builder.outdir
            j.tmpdir = builder.tmpdir
            j.stagedir = builder.stagedir

        inplaceUpdateReq = self.get_requirement("http://commonwl.org/cwltool#InplaceUpdateRequirement")[0]

        if inplaceUpdateReq:
            j.inplace_update = inplaceUpdateReq["inplaceUpdate"]
        normalizeFilesDirs(j.generatefiles)

        readers = {}  # type: Dict[Text, Any]
        muts = set()  # type: Set[Text]

        if builder.mutation_manager:
            def register_mut(f):
                muts.add(f["location"])
                builder.mutation_manager.register_mutation(j.name, f)

            def register_reader(f):
                if f["location"] not in muts:
                    builder.mutation_manager.register_reader(j.name, f)
                    readers[f["location"]] = copy.deepcopy(f)

            for li in j.generatefiles["listing"]:
                li = cast(Dict[Text, Any], li)
                if li.get("writable") and j.inplace_update:
                    adjustFileObjs(li, register_mut)
                    adjustDirObjs(li, register_mut)
                else:
                    adjustFileObjs(li, register_reader)
                    adjustDirObjs(li, register_reader)

            adjustFileObjs(builder.files, register_reader)
            adjustFileObjs(builder.bindings, register_reader)
            adjustDirObjs(builder.files, register_reader)
            adjustDirObjs(builder.bindings, register_reader)

        timelimit = self.get_requirement(require_prefix+"TimeLimit")[0]
        if timelimit:
            with SourceLine(timelimit, "timelimit", validate.ValidationException, debug):
                j.timelimit = builder.do_eval(timelimit["timelimit"])
                if not isinstance(j.timelimit, int) or j.timelimit < 0:
                    raise Exception("timelimit must be an integer >= 0, got: %s" % j.timelimit)

        if self.metadata["cwlVersion"] == "v1.0":
            j.networkaccess = True
        networkaccess = self.get_requirement(require_prefix+"NetworkAccess")[0]
        if networkaccess:
            with SourceLine(networkaccess, "networkAccess", validate.ValidationException, debug):
                j.networkaccess = builder.do_eval(networkaccess["networkAccess"])
                if not isinstance(j.networkaccess, bool):
                    raise Exception("networkAccess must be a boolean, got: %s" % j.networkaccess)

        j.environment = {}
        evr = self.get_requirement("EnvVarRequirement")[0]
        if evr:
            for t in evr["envDef"]:
                j.environment[t["envName"]] = builder.do_eval(t["envValue"])

        shellcmd = self.get_requirement("ShellCommandRequirement")[0]
        if shellcmd:
            cmd = []  # type: List[Text]
            for b in builder.bindings:
                arg = builder.generate_arg(b)
                if b.get("shellQuote", True):
                    arg = [shellescape.quote(a) for a in aslist(arg)]
                cmd.extend(aslist(arg))
            j.command_line = ["/bin/sh", "-c", " ".join(cmd)]
        else:
            j.command_line = flatten(list(map(builder.generate_arg, builder.bindings)))

        j.pathmapper = builder.pathmapper
        j.collect_outputs = partial(
            self.collect_output_ports, self.tool["outputs"], builder,
            compute_checksum=getdefault(runtimeContext.compute_checksum, True),
            jobname=jobname,
            readers=readers)
        j.output_callback = output_callbacks

        yield j

    def collect_output_ports(self,
                             ports,                  # type: Set[Dict[Text, Any]]
                             builder,                # type: Builder
                             outdir,                 # type: Text
                             compute_checksum=True,  # type: bool
                             jobname="",             # type: Text
                             readers=None            # type: Dict[Text, Any]
                            ):  # type: (...) -> OutputPorts
        ret = {}  # type: OutputPorts
        debug = _logger.isEnabledFor(logging.DEBUG)
        try:
            fs_access = builder.make_fs_access(outdir)
            custom_output = fs_access.join(outdir, "cwl.output.json")
            if fs_access.exists(custom_output):
                with fs_access.open(custom_output, "r") as f:
                    ret = json.load(f)
                if debug:
                    _logger.debug(u"Raw output from %s: %s", custom_output,
                                  json_dumps(ret, indent=4))
            else:
                for i, port in enumerate(ports):
                    def makeWorkflowException(msg):
                        return WorkflowException(
                            u"Error collecting output for parameter '%s':\n%s"
                            % (shortname(port["id"]), msg))
                    with SourceLine(ports, i, makeWorkflowException, debug):
                        fragment = shortname(port["id"])
                        ret[fragment] = self.collect_output(port, builder, outdir, fs_access,
                                                            compute_checksum=compute_checksum)
            if ret:
                revmap = partial(revmap_file, builder, outdir)
                adjustDirObjs(ret, trim_listing)
                visit_class(ret, ("File", "Directory"), cast(Callable[[Any], Any], revmap))
                visit_class(ret, ("File", "Directory"), remove_path)
                normalizeFilesDirs(ret)
                visit_class(ret, ("File", "Directory"), partial(check_valid_locations, fs_access))

                if compute_checksum:
                    adjustFileObjs(ret, partial(compute_checksums, fs_access))

            validate.validate_ex(
                self.names.get_name("outputs_record_schema", ""), ret,
                strict=False, logger=_logger_validation_warnings)
            if ret is not None and builder.mutation_manager is not None:
                adjustFileObjs(ret, builder.mutation_manager.set_generation)
            return ret if ret is not None else {}
        except validate.ValidationException as e:
            raise WorkflowException(
                "Error validating output record. " + Text(e) + "\n in " +
                json_dumps(ret, indent=4))
        finally:
            if builder.mutation_manager and readers:
                for r in readers.values():
                    builder.mutation_manager.release_reader(jobname, r)

    def collect_output(self,
                       schema,                # type: Dict[Text, Any]
                       builder,               # type: Builder
                       outdir,                # type: Text
                       fs_access,             # type: StdFsAccess
                       compute_checksum=True  # type: bool
                      ):
        # type: (...) -> Optional[Union[Dict[Text, Any], List[Union[Dict[Text, Any], Text]]]]
        r = []  # type: List[Any]
        empty_and_optional = False
        debug = _logger.isEnabledFor(logging.DEBUG)
        if "outputBinding" in schema:
            binding = schema["outputBinding"]
            globpatterns = []  # type: List[Text]

            revmap = partial(revmap_file, builder, outdir)

            if "glob" in binding:
                with SourceLine(binding, "glob", WorkflowException, debug):
                    for gb in aslist(binding["glob"]):
                        gb = builder.do_eval(gb)
                        if gb:
                            globpatterns.extend(aslist(gb))

                    for gb in globpatterns:
                        if gb.startswith(outdir):
                            gb = gb[len(outdir) + 1:]
                        elif gb == ".":
                            gb = outdir
                        elif gb.startswith("/"):
                            raise WorkflowException(
                                "glob patterns must not start with '/'")
                        try:
                            prefix = fs_access.glob(outdir)
                            r.extend([{"location": g,
                                       "path": fs_access.join(builder.outdir,
                                           g[len(prefix[0])+1:]),
                                       "basename": os.path.basename(g),
                                       "nameroot": os.path.splitext(
                                           os.path.basename(g))[0],
                                       "nameext": os.path.splitext(
                                           os.path.basename(g))[1],
                                       "class": "File" if fs_access.isfile(g)
                                       else "Directory"}
                                      for g in sorted(fs_access.glob(
                                          fs_access.join(outdir, gb)),
                                          key=cmp_to_key(cast(
                                              Callable[[Text, Text],
                                                  int], locale.strcoll)))])
                        except (OSError, IOError) as e:
                            _logger.warning(Text(e))
                        except Exception:
                            _logger.error("Unexpected error from fs_access", exc_info=True)
                            raise

                for files in r:
                    rfile = files.copy()
                    revmap(rfile)
                    if files["class"] == "Directory":
                        ll = builder.loadListing or (binding and binding.get("loadListing"))
                        if ll and ll != "no_listing":
                            get_listing(fs_access, files, (ll == "deep_listing"))
                    else:
                        with fs_access.open(rfile["location"], "rb") as f:
                            contents = b""
                            if binding.get("loadContents") or compute_checksum:
                                contents = f.read(CONTENT_LIMIT)
                            if binding.get("loadContents"):
                                files["contents"] = contents.decode("utf-8")
                            if compute_checksum:
                                checksum = hashlib.sha1()
                                while contents != b"":
                                    checksum.update(contents)
                                    contents = f.read(1024 * 1024)
                                files["checksum"] = "sha1$%s" % checksum.hexdigest()
                        files["size"] = fs_access.size(rfile["location"])

            optional = False
            single = False
            if isinstance(schema["type"], MutableSequence):
                if "null" in schema["type"]:
                    optional = True
                if "File" in schema["type"] or "Directory" in schema["type"]:
                    single = True
            elif schema["type"] == "File" or schema["type"] == "Directory":
                single = True

            if "outputEval" in binding:
                with SourceLine(binding, "outputEval", WorkflowException, debug):
                    r = builder.do_eval(binding["outputEval"], context=r)

            if single:
                if not r and not optional:
                    with SourceLine(binding, "glob", WorkflowException, debug):
                        raise WorkflowException("Did not find output file with glob pattern: '{}'".format(globpatterns))
                elif not r and optional:
                    pass
                elif isinstance(r, MutableSequence):
                    if len(r) > 1:
                        raise WorkflowException("Multiple matches for output item that is a single file.")
                    else:
                        r = r[0]

            if "secondaryFiles" in schema:
                with SourceLine(schema, "secondaryFiles", WorkflowException, debug):
                    for primary in aslist(r):
                        if isinstance(primary, MutableMapping):
                            primary.setdefault("secondaryFiles", [])
                            pathprefix = primary["path"][0:primary["path"].rindex("/")+1]
                            for sf in aslist(schema["secondaryFiles"]):
                                if isinstance(sf, MutableMapping) or "$(" in sf or "${" in sf:
                                    sfpath = builder.do_eval(sf, context=primary)
                                    subst = False
                                else:
                                    sfpath = sf
                                    subst = True
                                for sfitem in aslist(sfpath):
                                    if isinstance(sfitem, string_types):
                                        if subst:
                                            sfitem = {"path": substitute(primary["path"], sfitem)}
                                        else:
                                            sfitem = {"path": pathprefix+sfitem}
                                    if "path" in sfitem and "location" not in sfitem:
                                        revmap(sfitem)
                                    if fs_access.isfile(sfitem["location"]):
                                        sfitem["class"] = "File"
                                        primary["secondaryFiles"].append(sfitem)
                                    elif fs_access.isdir(sfitem["location"]):
                                        sfitem["class"] = "Directory"
                                        primary["secondaryFiles"].append(sfitem)

            if "format" in schema:
                for primary in aslist(r):
                    primary["format"] = builder.do_eval(schema["format"], context=primary)

            # Ensure files point to local references outside of the run environment
            adjustFileObjs(r, revmap)

            if not r and optional:
                return None

        if (not empty_and_optional and isinstance(schema["type"], MutableMapping)
                and schema["type"]["type"] == "record"):
            out = {}
            for f in schema["type"]["fields"]:
                out[shortname(f["name"])] = self.collect_output(  # type: ignore
                    f, builder, outdir, fs_access,
                    compute_checksum=compute_checksum)
            return out
        return r
