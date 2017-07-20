from __future__ import absolute_import
import io
import json
import os
import shutil
import tempfile
import logging

_logger = logging.getLogger("cwltool")

METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
MAIN = os.path.join(WORKFLOW, "main")
SNAPSHOT = "snapshot"
PROVENANCE = os.path.join(METADATA, "provenance")

class RO():
    def __init__(self, tmpPrefix="tmp"):
        self.folder = tempfile.mkdtemp(prefix=tmpPrefix)
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))
        _logger.info("Temporary research object: %s", self.folder)

    def packed_workflow(self, packed):
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        f = open(path, "w")
        f.write(packed.encode("UTF8"))
        f.close()

    def close(self, folder):
        """Close the Research Object after saving to specified folder.

        This function can only be called once, after which this object
        can no longer be used.
        """
        # TODO: Write manifest and bagit metadata
        # TODO: Add to archive (.zip or .tar)
        shutil.move(self.folder, folder)
        # Forget about our tempfolder which no longer exists
        self.folder = None

def create_ro(tmpPrefix):
    return RO(tmpPrefix)

