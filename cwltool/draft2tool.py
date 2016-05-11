import avro.schema
import json
import copy
from .flatten import flatten
from functools import partial
import os
from .pathmapper import PathMapper, DockerPathMapper
from .job import CommandLineJob
import yaml
import glob
import logging
import hashlib
import random
from .process import Process, shortname, uniquename, adjustFileObjs
from .errors import WorkflowException
import schema_salad.validate as validate
from .utils import aslist
from . import expression
import re
import urlparse
import tempfile
from .builder import CONTENT_LIMIT, substitute, Builder
import shellescape
import errno
from typing import Callable, Any, Union, Generator, cast
import hashlib
import shutil

_logger = logging.getLogger("cwltool")

class ExpressionTool(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[str,List[None]], **Any) -> None
        super(ExpressionTool, self).__init__(toolpath_object, **kwargs)

    class ExpressionJob(object):

        def __init__(self):  # type: () -> None
            self.builder = None  # type: Builder
            self.requirements = None  # type: Dict[str,str]
            self.hints = None  # type: Dict[str,str]
            self.collect_outputs = None  # type: Callable[[Any], Any]
            self.output_callback = None  # type: Callable[[Any, Any], Any]
            self.outdir = None  # type: str
            self.tmpdir = None  # type: str
            self.script = None  # type: Dict[str,str]

        def run(self, **kwargs):  # type: (**Any) -> None
            try:
                self.output_callback(self.builder.do_eval(self.script), "success")
            except Exception as e:
                _logger.warn(u"Failed to evaluate expression:\n%s", e, exc_info=(e if kwargs.get('debug') else False))
                self.output_callback({}, "permanentFail")

    def job(self, joborder, input_basedir, output_callback, **kwargs):
        # type: (Dict[str,str], str, Callable[[Any, Any], Any], **Any) -> Generator[ExpressionTool.ExpressionJob, None, None]
        builder = self._init_job(joborder, input_basedir, **kwargs)

        j = ExpressionTool.ExpressionJob()
        j.builder = builder
        j.script = self.tool["expression"]
        j.output_callback = output_callback
        j.requirements = self.requirements
        j.hints = self.hints
        j.outdir = None
        j.tmpdir = None

        yield j


def remove_hostfs(f):  # type: (Dict[str, Any]) -> None
    if "hostfs" in f:
        del f["hostfs"]


def revmap_file(builder, outdir, f):
    # type: (Builder,str,Dict[str,Any]) -> Union[Dict[str,Any],None]
    """Remap a file back to original path. For Docker, this is outside the container.

    Uses either files in the pathmapper or remaps internal output directories
    to the external directory.
    """

    if f.get("hostfs"):
        return None

    revmap_f = builder.pathmapper.reversemap(f["path"])
    if revmap_f:
        f["path"] = revmap_f[1]
        f["hostfs"] = True
        return f
    elif f["path"].startswith(builder.outdir):
        f["path"] = os.path.join(outdir, f["path"][len(builder.outdir)+1:])
        f["hostfs"] = True
        return f
    else:
        raise WorkflowException(u"Output file path %s must be within designated output directory (%s) or an input file pass through." % (f["path"], builder.outdir))

class CallbackJob(object):
    def __init__(self, job, output_callback, cachebuilder, jobcache):
        # type: (CommandLineTool, Callable[[Any, Any], Any], Builder, str) -> None
        self.job = job
        self.output_callback = output_callback
        self.cachebuilder = cachebuilder
        self.outdir = jobcache

    def run(self, **kwargs):
        # type: (**Any) -> None
        self.output_callback(self.job.collect_output_ports(self.job.tool["outputs"],
                                                           self.cachebuilder, self.outdir),
                                            "success")


class CommandLineTool(Process):
    def __init__(self, toolpath_object, **kwargs):
        # type: (Dict[str,Any], **Any) -> None
        super(CommandLineTool, self).__init__(toolpath_object, **kwargs)

    def makeJobRunner(self):  # type: () -> CommandLineJob
        return CommandLineJob()

    def makePathMapper(self, reffiles, input_basedir, **kwargs):
        # type: (Set[str], str, **Any) -> PathMapper
        dockerReq, _ = self.get_requirement("DockerRequirement")
        try:
            if dockerReq and kwargs.get("use_container"):
                return DockerPathMapper(reffiles, input_basedir)
            else:
                return PathMapper(reffiles, input_basedir)
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise WorkflowException(u"Missing input file %s" % e)

    def job(self, joborder, input_basedir, output_callback, **kwargs):
        # type: (Dict[str,str], str, Callable[..., Any], **Any) -> Generator[Union[CommandLineJob, CallbackJob], None, None]

        jobname = uniquename(kwargs.get("name", shortname(self.tool.get("id", "job"))))

        if kwargs.get("cachedir"):
            cacheargs = kwargs.copy()
            cacheargs["outdir"] = "/out"
            cacheargs["tmpdir"] = "/tmp"
            cachebuilder = self._init_job(joborder, input_basedir, **cacheargs)
            cachebuilder.pathmapper = PathMapper(set((f["path"] for f in cachebuilder.files)),
                                                 input_basedir)

            cmdline = flatten(map(cachebuilder.generate_arg, cachebuilder.bindings))
            (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
            if docker_req and kwargs.get("use_container") is not False:
                dockerimg = docker_req.get("dockerImageId") or docker_req.get("dockerPull")
                cmdline = ["docker", "run", dockerimg] + cmdline
            keydict = {"cmdline": cmdline}

            for _,f in cachebuilder.pathmapper.items():
                st = os.stat(f[0])
                keydict[f[0]] = [st.st_size, int(st.st_mtime * 1000)]

            interesting = {"DockerRequirement",
                           "EnvVarRequirement",
                           "CreateFileRequirement",
                           "ShellCommandRequirement"}
            for rh in (self.requirements, self.hints):
                for r in reversed(rh):
                    if r["class"] in interesting and r["class"] not in keydict:
                        keydict[r["class"]] = r

            keydictstr = json.dumps(keydict, separators=(',',':'), sort_keys=True)
            cachekey = hashlib.md5(keydictstr).hexdigest()

            _logger.debug("[job %s] keydictstr is %s -> %s", jobname, keydictstr, cachekey)

            jobcache = os.path.join(kwargs["cachedir"], cachekey)
            jobcachepending = jobcache + ".pending"

            if os.path.isdir(jobcache) and not os.path.isfile(jobcachepending):
                if docker_req and kwargs.get("use_container") is not False:
                    cachebuilder.outdir = kwargs.get("docker_outdir") or "/var/spool/cwl"
                else:
                    cachebuilder.outdir = jobcache

                _logger.info("[job %s] Using cached output in %s", jobname, jobcache)
                yield CallbackJob(self, output_callback, cachebuilder, jobcache)
                return
            else:
                _logger.info("[job %s] Output of job will be cached in %s", jobname, jobcache)
                shutil.rmtree(jobcache, True)
                os.makedirs(jobcache)
                kwargs["outdir"] = jobcache
                open(jobcachepending, "w").close()
                def rm_pending_output_callback(output_callback, jobcachepending,
                                               outputs, processStatus):
                    if processStatus == "success":
                        os.remove(jobcachepending)
                    output_callback(outputs, processStatus)
                output_callback = cast(
                        Callable[..., Any],  # known bug in mypy
                        # https://github.com/python/mypy/issues/797
                        partial(rm_pending_output_callback, output_callback,
                            jobcachepending))

        builder = self._init_job(joborder, input_basedir, **kwargs)

        reffiles = set((f["path"] for f in builder.files))

        j = self.makeJobRunner()
        j.builder = builder
        j.joborder = builder.job
        j.stdin = None
        j.stdout = None
        j.successCodes = self.tool.get("successCodes")
        j.temporaryFailCodes = self.tool.get("temporaryFailCodes")
        j.permanentFailCodes = self.tool.get("permanentFailCodes")
        j.requirements = self.requirements
        j.hints = self.hints
        j.name = jobname

        _logger.debug(u"[job %s] initializing from %s%s",
                     j.name,
                     self.tool.get("id", ""),
                     u" as part of %s" % kwargs["part_of"] if "part_of" in kwargs else "")
        _logger.debug(u"[job %s] %s", j.name, json.dumps(joborder, indent=4))


        builder.pathmapper = None

        if self.tool.get("stdin"):
            j.stdin = builder.do_eval(self.tool["stdin"])
            reffiles.add(j.stdin)

        if self.tool.get("stdout"):
            j.stdout = builder.do_eval(self.tool["stdout"])
            if os.path.isabs(j.stdout) or ".." in j.stdout:
                raise validate.ValidationException("stdout must be a relative path")

        builder.pathmapper = self.makePathMapper(reffiles, input_basedir, **kwargs)
        builder.requirements = j.requirements

        # map files to assigned path inside a container. We need to also explicitly
        # walk over input as implicit reassignment doesn't reach everything in builder.bindings
        def _check_adjust(f):  # type: (Dict[str,Any]) -> Dict[str,Any]
            if not f.get("containerfs"):
                f["path"] = builder.pathmapper.mapper(f["path"])[1]
                f["containerfs"] = True
            return f

        _logger.debug(u"[job %s] path mappings is %s", j.name, json.dumps({p: builder.pathmapper.mapper(p) for p in builder.pathmapper.files()}, indent=4))

        adjustFileObjs(builder.files, _check_adjust)
        adjustFileObjs(builder.bindings, _check_adjust)

        _logger.debug(u"[job %s] command line bindings is %s", j.name, json.dumps(builder.bindings, indent=4))

        dockerReq = self.get_requirement("DockerRequirement")[0]
        if dockerReq and kwargs.get("use_container"):
            out_prefix = kwargs.get("tmp_outdir_prefix")
            j.outdir = kwargs.get("outdir") or tempfile.mkdtemp(prefix=out_prefix)
            tmpdir_prefix = kwargs.get('tmpdir_prefix')
            j.tmpdir = kwargs.get("tmpdir") or tempfile.mkdtemp(prefix=tmpdir_prefix)
        else:
            j.outdir = builder.outdir
            j.tmpdir = builder.tmpdir

        createFiles = self.get_requirement("CreateFileRequirement")[0]
        j.generatefiles = {}
        if createFiles:
            for t in createFiles["fileDef"]:
                j.generatefiles[builder.do_eval(t["filename"])] = copy.deepcopy(builder.do_eval(t["fileContent"]))

        j.environment = {}
        evr = self.get_requirement("EnvVarRequirement")[0]
        if evr:
            for t in evr["envDef"]:
                j.environment[t["envName"]] = builder.do_eval(t["envValue"])

        shellcmd = self.get_requirement("ShellCommandRequirement")[0]
        if shellcmd:
            cmd = []  # type: List[str]
            for b in builder.bindings:
                arg = builder.generate_arg(b)
                if b.get("shellQuote", True):
                    arg = [shellescape.quote(a) for a in aslist(arg)]
                cmd.extend(aslist(arg))
            j.command_line = ["/bin/sh", "-c", " ".join(cmd)]
        else:
            j.command_line = flatten(map(builder.generate_arg, builder.bindings))

        j.pathmapper = builder.pathmapper
        j.collect_outputs = partial(
                self.collect_output_ports, self.tool["outputs"], builder)
        j.output_callback = output_callback

        yield j

    def collect_output_ports(self, ports, builder, outdir):
        # type: (Set[Dict[str,Any]], Builder, str) -> Dict[str,Union[str,List[Any],Dict[str,Any]]]
        try:
            ret = {}  # type: Dict[str,Union[str,List[Any],Dict[str,Any]]]
            custom_output = os.path.join(outdir, "cwl.output.json")
            if builder.fs_access.exists(custom_output):
                with builder.fs_access.open(custom_output, "r") as f:
                    ret = yaml.load(f)
                _logger.debug(u"Raw output from %s: %s", custom_output, json.dumps(ret, indent=4))
                adjustFileObjs(ret, remove_hostfs)
                adjustFileObjs(ret,
                        cast(Callable[[Any], Any],  # known bug in mypy
                            # https://github.com/python/mypy/issues/797
                            partial(revmap_file, builder, outdir)))
                adjustFileObjs(ret, remove_hostfs)
                validate.validate_ex(self.names.get_name("outputs_record_schema", ""), ret)
                return ret

            for port in ports:
                fragment = shortname(port["id"])
                try:
                    ret[fragment] = self.collect_output(port, builder, outdir)
                except Exception as e:
                    raise WorkflowException(u"Error collecting output for parameter '%s': %s" % (shortname(port["id"]), e))
            if ret:
                adjustFileObjs(ret, remove_hostfs)
            validate.validate_ex(self.names.get_name("outputs_record_schema", ""), ret)
            return ret if ret is not None else {}
        except validate.ValidationException as e:
            raise WorkflowException("Error validating output record, " + str(e) + "\n in " + json.dumps(ret, indent=4))

    def collect_output(self, schema, builder, outdir):
        # type: (Dict[str,Any], Builder, str) -> Union[Dict[str, Any], List[Union[Dict[str, Any], str]]]
        r = []  # type: List[Any]
        if "outputBinding" in schema:
            binding = schema["outputBinding"]
            globpatterns = []  # type: List[str]

            revmap = partial(revmap_file, builder, outdir)

            if "glob" in binding:
                for gb in aslist(binding["glob"]):
                    gb = builder.do_eval(gb)
                    if gb:
                        globpatterns.extend(aslist(gb))

                for gb in globpatterns:
                    if gb.startswith(outdir):
                        gb = gb[len(outdir)+1:]
                    elif gb.startswith("/"):
                        raise WorkflowException("glob patterns must not start with '/'")
                    try:
                        r.extend([{"path": g, "class": "File", "hostfs": True}
                                  for g in builder.fs_access.glob(os.path.join(outdir, gb))])
                    except (OSError, IOError) as e:
                        _logger.warn(str(e))

                for files in r:
                    checksum = hashlib.sha1()
                    with builder.fs_access.open(files["path"], "rb") as f:
                        contents = f.read(CONTENT_LIMIT)
                        if binding.get("loadContents"):
                            files["contents"] = contents
                        filesize = 0
                        while contents != "":
                            checksum.update(contents)
                            filesize += len(contents)
                            contents = f.read(1024*1024)
                    files["checksum"] = "sha1$%s" % checksum.hexdigest()
                    files["size"] = filesize
                    if "format" in schema:
                        files["format"] = builder.do_eval(schema["format"], context=files)

            optional = False
            singlefile = False
            if isinstance(schema["type"], list):
                if "null" in schema["type"]:
                    optional = True
                if "File" in schema["type"]:
                    singlefile = True
            elif schema["type"] == "File":
                singlefile = True

            if "outputEval" in binding:
                eout = builder.do_eval(binding["outputEval"], context=r)
                if singlefile:
                    # Handle single file outputs not wrapped in a list
                    if eout is not None and not isinstance(eout, (list, tuple)):
                        r = [eout]
                    elif optional and eout is None:
                        pass
                    elif (eout is None or len(eout) != 1 or
                            not isinstance(eout[0], dict)
                            or "path" not in eout[0]):
                        raise WorkflowException(
                            u"Expression must return a file object for %s."
                            % schema["id"])
                    else:
                        r = [eout]
                else:
                    r = eout

            if singlefile:
                if not r and not optional:
                    raise WorkflowException("Did not find output file with glob pattern: '{}'".format(globpatterns))
                elif not r and optional:
                    pass
                elif isinstance(r, list):
                    if len(r) > 1:
                        raise WorkflowException("Multiple matches for output item that is a single file.")
                    else:
                        r = r[0]

            # Ensure files point to local references outside of the run environment
            adjustFileObjs(r, cast(  # known bug in mypy
                # https://github.com/python/mypy/issues/797
                Callable[[Any], Any], revmap))

            if "secondaryFiles" in schema:
                for primary in aslist(r):
                    if isinstance(primary, dict):
                        primary["secondaryFiles"] = []
                        for sf in aslist(schema["secondaryFiles"]):
                            if isinstance(sf, dict) or "$(" in sf or "${" in sf:
                                sfpath = builder.do_eval(sf, context=r)
                                if isinstance(sfpath, basestring):
                                    sfpath = revmap({"path": sfpath, "class": "File"})
                            else:
                                sfpath = {"path": substitute(primary["path"], sf), "class": "File", "hostfs": True}

                            for sfitem in aslist(sfpath):
                                if builder.fs_access.exists(sfitem["path"]):
                                    primary["secondaryFiles"].append(sfitem)

            if not r and optional:
                r = None

        if (not r and isinstance(schema["type"], dict) and
                schema["type"]["type"] == "record"):
            out = {}
            for f in schema["type"]["fields"]:
                out[shortname(f["name"])] = self.collect_output(  # type: ignore
                        f, builder, outdir)
            return out
        return r
