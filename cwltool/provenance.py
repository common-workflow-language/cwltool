from __future__ import absolute_import
import io
import json
import os
import os.path
import posixpath
import shutil
import tempfile
import logging
import hashlib
from shutil import copyfile
import io
import ruamel.yaml as yaml
import warnings
warnings.simplefilter('ignore', yaml.error.UnsafeLoaderWarning)

_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "metadata"
DATA = "data"
OUTPUT= "output"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")

class ProvenanceException(BaseException):
    pass

## sha1, compatible with the File type's "checksum" field
## e.g. "checksum" = "sha1$47a013e660d408619d894b20806b1d5086aab03b"
## See ./cwltool/schemas/v1.0/Process.yml
hashmethod = hashlib.sha1

class RO():
    def __init__(self, tmpPrefix="tmp"):
        self.folder = tempfile.mkdtemp(prefix=tmpPrefix)
        self.tmpPrefix = tmpPrefix
        self._initialize()
        _logger.info(u"[provenance] Temporary research object: %s", self.folder)

    def _initialize(self):
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))

    def _finalize(self):
        # TODO: Write manifest and bagit metadata
#        _logger.info(u"[provenance] Generated research object manifest: %s", self.folder)
        pass
    def PROVfileGeneration(self):
        #TODO: this is going to generate all the namespaces and initial structure of the PROV document
        pass
    def retrieve_info(self, packedFile):
        steps_wfRun= []
        with open(packedFile, 'r') as stream:
            try:
                arguments=yaml.load(stream)
                #if $graph is in yaml document
                if "$graph" in arguments:
                    for step in arguments["$graph"][0]["steps"]:
                        steps_wfRun.append(step["id"])
                else: #otherwise use this block
                    for step in arguments:
                        if step=="steps":
                            for each in arguments[step]:
                                steps_wfRun.append(each['id'])
                _logger.info(u"[provenance] WorkflowSteps Generated: %s", steps_wfRun)
                return steps_wfRun
            except yaml.YAMLError as exc:
                _logger.warning(exc)

    def packed_workflow(self, packed):
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        with open (path, "w") as f:
            # YAML is always UTF8
            f.write(packed.encode("UTF-8"))
        _logger.info(u"[provenance] Added packed workflow: %s", path)
        workflowSteps=self.retrieve_info(path)
        return (path, workflowSteps)

    def _checksum_copy(self, fp, copy_to_fp=None,
                       hashmethod=hashmethod, buffersize=1024*1024):
        checksum = hashmethod()
        contents = fp.read(buffersize)
        while contents != b"":
            if copy_to_fp is not None:
                copy_to_fp.write(contents)
            checksum.update(contents)
            contents = fp.read(buffersize)
        if copy_to_fp is not None:
            copy_to_fp.flush()
        return checksum.hexdigest().lower()


    def add_data_file(self, from_fp):
        with tempfile.NamedTemporaryFile(
                 prefix=self.tmpPrefix, delete=False) as tmp:
            checksum = self._checksum_copy(from_fp, tmp)

        # Calculate hash-based file path
        folder = os.path.join(self.folder, DATA, checksum[0:2])
        path = os.path.join(folder, checksum)

        # os.rename assumed safe, as our temp file should
        # be in same file system as our temp folder
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.rename(tmp.name, path)

        # Relative posix path
        # (to avoid \ on Windows)
        rel_path = self._posix_path(os.path.relpath(path, self.folder))

        # Register in bagit checksum
        if hashmethod == hashlib.sha1:
            self._add_to_bagit(rel_path, sha1=checksum)
        else:
            _logger.warning(u"[provenance] Unknown hash method %s for bagit manifest",
                hashmethod)
            # Inefficient, bagit support need to checksum again
            self._add_to_bagit(rel_path)
        _logger.info(u"[provenance] Added data file %s", path)
        return rel_path

    def _convert_path(self, path, from_path=os.path, to_path=posixpath):
        if from_path == to_path:
            return path
        if (from_path.isabs(path)):
            raise ProvenanceException("path must be relative: %s" % path)
            # ..as it might include system paths like "C:\" or /tmp
        split = path.split(from_path.sep)
        converted = to_path.sep.join(split)
        return converted

    def _posix_path(self, local_path):
        return self._convert_path(local_path, os.path, posixpath)

    def _local_path(self, posix_path):
        return self._convert_path(posix_path, posixpath, os.path)

    def _add_to_bagit(self, rel_path, **checksums):
        if (posixpath.isabs(rel_path)):
            raise ProvenanceException("rel_path must be relative: %s" % rel_path)
        local_path = os.path.join(self.folder, self._local_path(rel_path))
        if not os.path.exists(local_path):
            raise ProvenanceException("File %s does not exist within RO: %s" % rel_path, local_path)

        if not "sha1" in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(local_path) as fp:
                checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)

        # Add checksums to corresponding manifest files
        for (method,hash) in checksums.items():
            # Quite naive for now - assume file is not already listed in manifest
            manifest = os.path.join(self.folder,
                "manifest-" + method.lower() + ".txt")
            with open(manifest, "a") as checksumFile:
                line = "%s %s\n" % (hash, rel_path)
                _logger.info(u"[provenance] Added to %s: %s", manifest, line)
                checksumFile.write(line)

    def create_job(self, job, kwargs):
        #TODO handle nested workflow at level 2 provenance
        #TODO customise the file
        '''
        This function takes the dictionary input object and generates
        a json file containing the relative paths and link to the associated
        cwl document
        '''
        self._relativise_files(job, kwargs)
        path=os.path.join(self.folder, WORKFLOW, "master-job.json")
        with open (path, "w") as f:
            json.dump(job, f)

        _logger.info(u"[provenance] Generated customised job file: %s", path)

    def _relativise_files(self, structure, kwargs):
        '''
        save any file objects into RO and update the local paths
        '''

        # Base case - we found a File we need to update
        _logger.debug(u"[provenance] Relativising: %s", structure)
        if isinstance(structure, dict):
            if structure.get("class") == "File":
                #standardised fs access object creation
                fsaccess = kwargs["make_fs_access"]("")
                # TODO: Replace location/path with new add_data_file() paths
                with fsaccess.open(structure["location"], "rb") as f:
                    relative_path=self.add_data_file(f)
                    structure["location"]= "../"+relative_path
            for o in structure.values():
                self._relativise_files(o, kwargs)
            return

        if isinstance(structure, str) or isinstance(structure, unicode):
            # Just a string value, no need to iterate further
            return
        try:
            for o in iter(structure):
                # Recurse and rewrite any nested File objects
                self._relativise_files(o, kwargs)
        except TypeError:
            pass
#**************************************
    #copy output files to the RO
    def add_output(self, workflow_output=None, saveTo=None):
        if isinstance(workflow_output, dict):
            #Iterate over the output object, collect and relative the output file paths
            for item in workflow_output:
                if workflow_output[item]["class"] == "File":
                    outputfile_path= os.path.join(self.folder, OUTPUT, workflow_output[item]["checksum"][5:7])
                    path = os.path.join(outputfile_path, workflow_output[item]["checksum"])
                    if not os.path.isdir(path):
                        os.makedirs(path)
                    _logger.info("Moving output files to RO")
                    shutil.move(workflow_output[item]["location"][7:], path)

#**************************************

    def close(self, saveTo=None):
        """Close the Research Object, optionally saving to specified folder.

        Closing will remove any temporary files used by this research object.
        After calling this method, this ResearchObject instance can no longer
        be used, except for no-op calls to .close().

        The 'saveTo' folder should not exist - if it does, it will be deleted.

        It is safe to call this function multiple times without the
        'saveTo' argument, e.g. within a try..finally block to
        ensure the temporary files of this RO are removed.
        """
        if saveTo is None:
            if self.folder:
                _logger.info(u"[provenance] Deleting temporary %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            _logger.info(u"[provenance] Finalizing Research Object")
            self._finalize() # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(saveTo):
                _logger.info(u"[provenance] Deleting existing %s", saveTo)
                shutil.rmtree(saveTo)

            shutil.move(self.folder, saveTo)
            _logger.info(u"[provenance] Research Object saved to %s", saveTo)
        # Forget our temporary folder, which should no longer exists
        # This makes later close() a no-op
        self.folder = None

def create_ro(tmpPrefix):
    return RO(tmpPrefix)
