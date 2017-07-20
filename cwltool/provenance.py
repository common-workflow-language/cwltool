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
        self.initialize()
        _logger.info("Temporary research object: %s", self.folder)

    def _initialize(self):
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))

    def _finalize(self):
        # TODO: Write manifest and bagit metadata
        pass

    def packed_workflow(self, packed):
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        f = open(path, "w")
        # YAML is always UTF8
        f.write(packed.encode("UTF-8"))
        f.close()

    def close(self, folder=None):
        """Close the Research Object after saving to specified folder.

        If the argument 'folder' is None (the default value), the 
        research object will be removed without saving.

        This function can only be called once, after which this object
        can no longer be used.
        """
        if folder is None:
            shutil.rmtree(self.folder)
        else:
            self._finalize()
            # TODO: Add to archive (.zip or .tar)
            shutil.move(self.folder, folder)

        # Forget about our tempfolder which no longer exists
        self.folder = None

def create_ro(tmpPrefix):
    return RO(tmpPrefix)

