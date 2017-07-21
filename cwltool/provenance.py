from __future__ import absolute_import
import io
import json
import os
import shutil
import tempfile
import logging

_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")

class RO():
    def __init__(self, tmpPrefix="tmp"):
        self.folder = tempfile.mkdtemp(prefix=tmpPrefix)
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
        f = open(path, "w")
        # YAML is always UTF8
        f.write(packed.encode("UTF-8"))
        f.close()
        _logger.info(u"[provenance] Added packed workflow: %s", path)


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

