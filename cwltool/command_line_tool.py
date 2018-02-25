from __future__ import absolute_import
import copy
import hashlib
import locale
import json
import logging
import os
import re
import shutil
import tempfile
from functools import partial, cmp_to_key
from typing import (Any, Callable, Dict, Generator, List, Optional, Set, Text,
    Union, cast)

from six import string_types, u

import schema_salad.validate as validate
import shellescape
from schema_salad.ref_resolver import file_uri, uri_file_path
from schema_salad.sourceline import SourceLine, indent
from six.moves import urllib

from .builder import CONTENT_LIMIT, Builder, substitute
from .docker import DockerCommandLineJob
from .errors import WorkflowException
from .flatten import flatten
from .job import CommandLineJob, JobBase
from .pathmapper import (PathMapper, adjustDirObjs, adjustFileObjs,
                         get_listing, trim_listing, visit_class)
from .process import (Process, UnsupportedRequirement,
                      _logger_validation_warnings, compute_checksums,
                      normalizeFilesDirs, shortname, uniquename)
from .singularity import SingularityCommandLineJob
from .stdfsaccess import StdFsAccess
from .utils import aslist, docker_windows_path_adjust, convert_pathsep_to_unix, windows_default_container_id, onWindows
from six.moves import map

ACCEPTLIST_EN_STRICT_RE = re.compile(r"^[a-zA-Z0-9._+-]+$")
ACCEPTLIST_EN_RELAXED_RE = re.compile(r".*")  # Accept anything
ACCEPTLIST_RE = ACCEPTLIST_EN_STRICT_RE
DEFAULT_CONTAINER_MSG="""We are on Microsoft Windows and not all components of this CWL description have a
container specified. This means that these steps will be executed in the default container,
which is %s.

Note, this could affect portability if this CWL description relies on non-POSIX features
or commands in this container. For best results add the following to your CWL
description's hints section:

hints:
  DockerRequirement:
    dockerPull: %s
"""

_logger = logging.getLogger("cwltool")


class ExpressionTool(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[Text, Any], **Any) -> None
        super(ExpressionTool, self).__init__(toolpath_object, **kwargs)

    class ExpressionJob(object):

        def __init__(self):  # type: () -> None
            self.builder = None  # type: Builder
            self.requirements = None  # type: Dict[Text, Text]
            self.hints = None  # type: Dict[Text, Text]
            self.collect_outputs = None  # type: Callable[[Any], Any]
            self.output_callback = None  # type: Callable[[Any, Any], Any]
            self.outdir = None  # type: Text
            self.tmpdir = None  # type: Text
            self.script = None  # type: Dict[Text, Text]

        def run(self, **kwargs):  # type: (**Any) -> None
            try:
                ev = self.builder.do_eval(self.script)
                normalizeFilesDirs(ev)
                self.output_callback(ev, "success")
            except Exception as e:
                _logger.warning(u"Failed to evaluate expression:\n%s",
                             e, exc_info=kwargs.get('debug'))
                self.output_callback({}, "permanentFail")

    def job(self,
            job_order,  # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            **kwargs  # type: Any
            ):
        # type: (...) -> Generator[ExpressionTool.ExpressionJob, None, None]
        builder = self._init_job(job_order, **kwargs)

        j = ExpressionTool.ExpressionJob()
        j.builder = builder
        j.script = self.tool["expression"]
        j.output_callback = output_callbacks
        j.requirements = self.requirements
        j.hints = self.hints
        j.outdir = None
        j.tmpdir = None

        yield j


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

    def run(self, **kwargs):
        # type: (**Any) -> None
        self.output_callback(self.job.collect_output_ports(
            self.job.tool["outputs"],
            self.cachebuilder,
            self.outdir,
            kwargs.get("compute_checksum", True)), "success")


# map files to assigned path inside a container. We need to also explicitly
# walk over input as implicit reassignment doesn't reach everything in builder.bindings
def check_adjust(builder, f):
    # type: (Builder, Dict[Text, Any]) -> Dict[Text, Any]

    f["path"] = docker_windows_path_adjust(builder.pathmapper.mapper(f["location"])[1])
    f["dirname"], f["basename"] = os.path.split(f["path"])
    if f["class"] == "File":
        f["nameroot"], f["nameext"] = os.path.splitext(f["basename"])
    if not ACCEPTLIST_RE.match(f["basename"]):
        raise WorkflowException("Invalid filename: '%s' contains illegal characters" % (f["basename"]))
    return f

def check_valid_locations(fs_access, ob):
    if ob["location"].startswith("_:"):
        pass
    if ob["class"] == "File" and not fs_access.isfile(ob["location"]):
        raise validate.ValidationException("Does not exist or is not a File: '%s'" % ob["location"])
    if ob["class"] == "Directory" and not fs_access.isdir(ob["location"]):
        raise validate.ValidationException("Does not exist or is not a Directory: '%s'" % ob["location"])

class CommandLineTool(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[Text, Any], **Any) -> None
        super(CommandLineTool, self).__init__(toolpath_object, **kwargs)
        self.find_default_container = kwargs.get("find_default_container", None)

    def makeJobRunner(self, use_container=True, **kwargs):  # type: (Optional[bool], **Any) -> JobBase
        dockerReq, _ = self.get_requirement("DockerRequirement")
        if not dockerReq and use_container:
            if self.find_default_container:
                default_container = self.find_default_container(self)
                if default_container:
                    self.requirements.insert(0, {
                        "class": "DockerRequirement",
                        "dockerPull": default_container
                    })
                    dockerReq = self.requirements[0]
                    if default_container == windows_default_container_id and use_container and onWindows():
                        _logger.warning(DEFAULT_CONTAINER_MSG % (windows_default_container_id, windows_default_container_id))

        if dockerReq and use_container:
            if kwargs.get('singularity'):
                return SingularityCommandLineJob()
            else:
                return DockerCommandLineJob()
        else:
            for t in reversed(self.requirements):
                if t["class"] == "DockerRequirement":
                    raise UnsupportedRequirement(
                        "--no-container, but this CommandLineTool has "
                        "DockerRequirement under 'requirements'.")
            return CommandLineJob()

    def makePathMapper(self, reffiles, stagedir, **kwargs):
        # type: (List[Any], Text, **Any) -> PathMapper
        return PathMapper(reffiles, kwargs["basedir"], stagedir,
                          separateDirs=kwargs.get("separateDirs", True))

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
            job_order,  # type: Dict[Text, Text]
            output_callbacks,  # type: Callable[[Any, Any], Any]
            **kwargs  # type: Any
            ):
        # type: (...) -> Generator[Union[JobBase, CallbackJob], None, None]

        jobname = uniquename(kwargs.get("name", shortname(self.tool.get("id", "job"))))
        if kwargs.get("cachedir"):
            cacheargs = kwargs.copy()
            cacheargs["outdir"] = "/out"
            cacheargs["tmpdir"] = "/tmp"
            cacheargs["stagedir"] = "/stage"
            cachebuilder = self._init_job(job_order, **cacheargs)
            cachebuilder.pathmapper = PathMapper(cachebuilder.files,
                                                 kwargs["basedir"],
                                                 cachebuilder.stagedir,
                                                 separateDirs=False)
            _check_adjust = partial(check_adjust, cachebuilder)
            visit_class([cachebuilder.files, cachebuilder.bindings],
                       ("File", "Directory"), _check_adjust)

            cmdline = flatten(list(map(cachebuilder.generate_arg, cachebuilder.bindings)))
            (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
            if docker_req and kwargs.get("use_container"):
                dockerimg = docker_req.get("dockerImageId") or docker_req.get("dockerPull")
            elif kwargs.get("default_container", None) is not None and kwargs.get("use_container"):
                dockerimg = kwargs.get("default_container")
            else:
                dockerimg = None

            if dockerimg:
                cmdline = ["docker", "run", dockerimg] + cmdline
            keydict = {u"cmdline": cmdline}

            if "stdout" in self.tool:
                keydict["stdout"] = self.tool["stdout"]
            for location, f in cachebuilder.pathmapper.items():
                if f.type == "File":
                    checksum = next((e['checksum'] for e in cachebuilder.files
                            if 'location' in e and e['location'] == location
                            and 'checksum' in e
                            and e['checksum'] != 'sha1$hash'), None)
                    st = os.stat(f.resolved)
                    if checksum:
                        keydict[f.resolved] = [st.st_size, checksum]
                    else:
                        keydict[f.resolved] = [st.st_size, int(st.st_mtime * 1000)]

            interesting = {"DockerRequirement",
                           "EnvVarRequirement",
                           "CreateFileRequirement",
                           "ShellCommandRequirement"}
            for rh in (self.requirements, self.hints):
                for r in reversed(rh):
                    if r["class"] in interesting and r["class"] not in keydict:
                        keydict[r["class"]] = r

            keydictstr = json.dumps(keydict, separators=(',', ':'), sort_keys=True)
            cachekey = hashlib.md5(keydictstr.encode('utf-8')).hexdigest()

            _logger.debug("[job %s] keydictstr is %s -> %s", jobname,
                          keydictstr, cachekey)

            jobcache = os.path.join(kwargs["cachedir"], cachekey)
            jobcachepending = jobcache + ".pending"

            if os.path.isdir(jobcache) and not os.path.isfile(jobcachepending):
                if docker_req and kwargs.get("use_container"):
                    cachebuilder.outdir = kwargs.get("docker_outdir") or "/var/spool/cwl"
                else:
                    cachebuilder.outdir = jobcache

                _logger.info("[job %s] Using cached output in %s", jobname, jobcache)
                yield CallbackJob(self, output_callbacks, cachebuilder, jobcache)
                return
            else:
                _logger.info("[job %s] Output of job will be cached in %s", jobname, jobcache)
                shutil.rmtree(jobcache, True)
                os.makedirs(jobcache)
                kwargs["outdir"] = jobcache
                open(jobcachepending, "w").close()

                def rm_pending_output_callback(output_callbacks, jobcachepending,
                                               outputs, processStatus):
                    if processStatus == "success":
                        os.remove(jobcachepending)
                    output_callbacks(outputs, processStatus)

                output_callbacks = cast(
                    Callable[..., Any],  # known bug in mypy
                    # https://github.com/python/mypy/issues/797
                    partial(rm_pending_output_callback, output_callbacks,
                            jobcachepending))

        builder = self._init_job(job_order, **kwargs)

        reffiles = copy.deepcopy(builder.files)

        j = self.makeJobRunner(**kwargs)
        j.builder = builder
        j.joborder = builder.job
        j.make_pathmapper = self.makePathMapper
        j.stdin = None
        j.stderr = None
        j.stdout = None
        j.successCodes = self.tool.get("successCodes")
        j.temporaryFailCodes = self.tool.get("temporaryFailCodes")
        j.permanentFailCodes = self.tool.get("permanentFailCodes")
        j.requirements = self.requirements
        j.hints = self.hints
        j.name = jobname

        debug = _logger.isEnabledFor(logging.DEBUG)

        if debug:
            _logger.debug(u"[job %s] initializing from %s%s",
                          j.name,
                          self.tool.get("id", ""),
                          u" as part of %s" % kwargs["part_of"] if "part_of" in kwargs else "")
            _logger.debug(u"[job %s] %s", j.name, json.dumps(job_order, indent=4))

        builder.pathmapper = None
        make_path_mapper_kwargs = kwargs
        if "stagedir" in make_path_mapper_kwargs:
            make_path_mapper_kwargs = make_path_mapper_kwargs.copy()
            del make_path_mapper_kwargs["stagedir"]

        builder.pathmapper = self.makePathMapper(reffiles, builder.stagedir, **make_path_mapper_kwargs)
        builder.requirements = j.requirements

        _check_adjust = partial(check_adjust, builder)

        visit_class([builder.files, builder.bindings], ("File", "Directory"), _check_adjust)

        initialWorkdir = self.get_requirement("InitialWorkDirRequirement")[0]
        j.generatefiles = {"class": "Directory", "listing": [], "basename": ""}
        if initialWorkdir:
            ls = []  # type: List[Dict[Text, Any]]
            if isinstance(initialWorkdir["listing"], (str, Text)):
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
            j.generatefiles[u"listing"] = ls
            for l in ls:
                self.updatePathmap(builder.outdir, builder.pathmapper, l)
            visit_class([builder.files, builder.bindings], ("File", "Directory"), _check_adjust)

        if debug:
            _logger.debug(u"[job %s] path mappings is %s", j.name,
                          json.dumps({p: builder.pathmapper.mapper(p) for p in builder.pathmapper.files()}, indent=4))

        if self.tool.get("stdin"):
            with SourceLine(self.tool, "stdin", validate.ValidationException, debug):
                j.stdin = builder.do_eval(self.tool["stdin"])
                reffiles.append({"class": "File", "path": j.stdin})

        if self.tool.get("stderr"):
            with SourceLine(self.tool, "stderr", validate.ValidationException, debug):
                j.stderr = builder.do_eval(self.tool["stderr"])
                if os.path.isabs(j.stderr) or ".." in j.stderr:
                    raise validate.ValidationException("stderr must be a relative path, got '%s'" % j.stderr)

        if self.tool.get("stdout"):
            with SourceLine(self.tool, "stdout", validate.ValidationException, debug):
                j.stdout = builder.do_eval(self.tool["stdout"])
                if os.path.isabs(j.stdout) or ".." in j.stdout or not j.stdout:
                    raise validate.ValidationException("stdout must be a relative path, got '%s'" % j.stdout)

        if debug:
            _logger.debug(u"[job %s] command line bindings is %s", j.name, json.dumps(builder.bindings, indent=4))

        dockerReq = self.get_requirement("DockerRequirement")[0]
        if dockerReq and kwargs.get("use_container"):
            out_prefix = kwargs.get("tmp_outdir_prefix")
            j.outdir = kwargs.get("outdir") or tempfile.mkdtemp(prefix=out_prefix)
            tmpdir_prefix = kwargs.get('tmpdir_prefix')
            j.tmpdir = kwargs.get("tmpdir") or tempfile.mkdtemp(prefix=tmpdir_prefix)
            j.stagedir = tempfile.mkdtemp(prefix=tmpdir_prefix)
        else:
            j.outdir = builder.outdir
            j.tmpdir = builder.tmpdir
            j.stagedir = builder.stagedir

        inplaceUpdateReq = self.get_requirement("http://commonwl.org/cwltool#InplaceUpdateRequirement")[0]

        if inplaceUpdateReq:
            j.inplace_update = inplaceUpdateReq["inplaceUpdate"]
        normalizeFilesDirs(j.generatefiles)

        readers = {}
        muts = set()

        if builder.mutation_manager:
            def register_mut(f):
                muts.add(f["location"])
                builder.mutation_manager.register_mutation(j.name, f)

            def register_reader(f):
                if f["location"] not in muts:
                    builder.mutation_manager.register_reader(j.name, f)
                    readers[f["location"]] = f

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
            compute_checksum=kwargs.get("compute_checksum", True),
            jobname=jobname,
            readers=readers)
        j.output_callback = output_callbacks

        yield j

    def collect_output_ports(self, ports, builder, outdir, compute_checksum=True, jobname="", readers=None):
        # type: (Set[Dict[Text, Any]], Builder, Text, bool, Text, Dict[Text, Any]) -> Dict[Text, Union[Text, List[Any], Dict[Text, Any]]]
        ret = {}  # type: Dict[Text, Union[Text, List[Any], Dict[Text, Any]]]
        debug = _logger.isEnabledFor(logging.DEBUG)
        try:
            fs_access = builder.make_fs_access(outdir)
            custom_output = fs_access.join(outdir, "cwl.output.json")
            if fs_access.exists(custom_output):
                with fs_access.open(custom_output, "r") as f:
                    ret = json.load(f)
                if debug:
                    _logger.debug(u"Raw output from %s: %s", custom_output, json.dumps(ret, indent=4))
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

            validate.validate_ex(self.names.get_name("outputs_record_schema", ""), ret,
                                 strict=False, logger=_logger_validation_warnings)
            if ret is not None and builder.mutation_manager is not None:
                adjustFileObjs(ret, builder.mutation_manager.set_generation)
            return ret if ret is not None else {}
        except validate.ValidationException as e:
            raise WorkflowException("Error validating output record. " + Text(e) + "\n in " + json.dumps(ret, indent=4))
        finally:
            if builder.mutation_manager and readers:
                for r in readers.values():
                    builder.mutation_manager.release_reader(jobname, r)

    def collect_output(self, schema, builder, outdir, fs_access, compute_checksum=True):
        # type: (Dict[Text, Any], Builder, Text, StdFsAccess, bool) -> Union[Dict[Text, Any], List[Union[Dict[Text, Any], Text]]]
        r = []  # type: List[Any]
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
                        except:
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
                                files["contents"] = contents
                            if compute_checksum:
                                checksum = hashlib.sha1()
                                while contents != b"":
                                    checksum.update(contents)
                                    contents = f.read(1024 * 1024)
                                files["checksum"] = "sha1$%s" % checksum.hexdigest()
                            f.seek(0, 2)
                            filesize = f.tell()
                        files["size"] = filesize
                        if "format" in schema:
                            files["format"] = builder.do_eval(schema["format"], context=files)

            optional = False
            single = False
            if isinstance(schema["type"], list):
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
                elif isinstance(r, list):
                    if len(r) > 1:
                        raise WorkflowException("Multiple matches for output item that is a single file.")
                    else:
                        r = r[0]

            if "secondaryFiles" in schema:
                with SourceLine(schema, "secondaryFiles", WorkflowException, debug):
                    for primary in aslist(r):
                        if isinstance(primary, dict):
                            primary.setdefault("secondaryFiles", [])
                            pathprefix = primary["path"][0:primary["path"].rindex("/")+1]
                            for sf in aslist(schema["secondaryFiles"]):
                                if isinstance(sf, dict) or "$(" in sf or "${" in sf:
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

            # Ensure files point to local references outside of the run environment
            adjustFileObjs(r, cast(  # known bug in mypy
                # https://github.com/python/mypy/issues/797
                Callable[[Any], Any], revmap))

            if not r and optional:
                r = None

        if (not r and isinstance(schema["type"], dict) and schema["type"]["type"] == "record"):
            out = {}
            for f in schema["type"]["fields"]:
                out[shortname(f["name"])] = self.collect_output(  # type: ignore
                    f, builder, outdir, fs_access,
                    compute_checksum=compute_checksum)
            return out
        return r