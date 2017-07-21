from __future__ import absolute_import
import io
import json
import os
import shutil
import tempfile
import logging
import hashlib

_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")

hashmethod = hashlib.sha256

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

    def packed_workflow(self, packed):
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        with open (path, "w") as f:
            # YAML is always UTF8
            f.write(packed.encode("UTF-8"))
        _logger.info(u"[provenance] Added packed workflow: %s", path)


    def add_data_file(self, fp):
        with tempfile.NamedTemporaryFile(
                prefix=self.tmpPrefix, delete=False) as tmp:
            checksum = hashmethod()
            contents = fp.read(1024 * 1024)
            while contents != b"":
                tmp.write(contents)
                checksum.update(contents)
                contents = fp.read(1024 * 1024)

            tmp.seek(0, 2)
            filesize = tmp.tell()

        hex = checksum.hexdigest()
        folder = os.path.join(self.folder, DATA, hex[0:2])
        path = os.path.join(folder, hex)

        # os.rename should be safe, as our mkstemp file
        # should be in same file system as our
        # mkdtemp folder
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.rename(tmp.name, path)

        # Return relative path as URI
        # (We can't use os.path.join which would use \ on Windows)
        return DATA + "/" + hex[0:2] + "/" + hex

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
        _logger.info(u"[provenance] Relativising paths: %s", structure)
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


    def close(self, saveTo=None):
        """Close the Research Object after saving to specified folder.
        The 'saveTo' folder should not exist - if it does it will be deleted.

        If the argument 'saveTo' is None (the default value), the
        research object will be removed without saving.

        This function can only be called once, after which this object
        can no longer be used. Later calls to this function will be no-op.
        """
        if saveTo is None:
            if self.folder:
                _logger.info(u"[provenance] Deleting %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            _logger.info(u"[provenance] Finalizing Research Object")
            self._finalize() # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(saveTo):
                shutil.rmtree(saveTo)
            shutil.move(self.folder, saveTo)
            _logger.info(u"[provenance] Research Object saved to %s", saveTo)

        # Forget about our temporary, which no longer exists
        self.folder = None

def create_ro(tmpPrefix):
    return RO(tmpPrefix)
