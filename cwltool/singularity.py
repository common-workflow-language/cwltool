from __future__ import absolute_import
import logging
import os
import re
import subprocess
import sys
from typing import Dict, List, Text

from .errors import WorkflowException

_logger = logging.getLogger("cwltool")


def get_image(dockerRequirement, pull_image, dry_run=False):
    # type: (Dict[Text, Text], bool, bool) -> bool
    found = False

    if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
        match = re.search(pattern=r'([a-z]*://)',string=dockerRequirement["dockerPull"])
        if match:
            dockerRequirement["dockerImageId"] = re.sub(pattern=r'([a-z]*://)', repl=r'', string=dockerRequirement["dockerPull"])
            dockerRequirement["dockerImageId"] = re.sub(pattern=r'[:/]', repl=r'-', string=dockerRequirement["dockerImageId"]) + ".img"
        else:
            dockerRequirement["dockerImageId"] = re.sub(pattern=r'[:/]', repl=r'-', string=dockerRequirement["dockerPull"]) + ".img"
            dockerRequirement["dockerPull"] = "docker://" + dockerRequirement["dockerPull"]

    # check to see if the Singularity container is already downloaded
    if os.path.isfile(dockerRequirement["dockerImageId"]):
        _logger.info("Using local copy of Singularity image")
        found = True

    # if the .img file is not already present, pull the image
    elif pull_image:
        cmd = []  # type: List[Text]
        if "dockerPull" in dockerRequirement:
            cmd = ["singularity", "pull", "--name", str(dockerRequirement["dockerImageId"]), str(dockerRequirement["dockerPull"])]
            _logger.info(Text(cmd))
            if not dry_run:
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True

    return found


def get_from_requirements(r, req, pull_image, dry_run=False):
    # type: (Dict[Text, Text], bool, bool, bool) -> Text
    # returns the filename of the Singularity image (e.g. hello-world-latest.img)
    if r:
        errmsg = None
        try:
            subprocess.check_output(["singularity", "--version"])
        except subprocess.CalledProcessError as e:
            errmsg = "Cannot execute 'singularity --version' " + Text(e)
        except OSError as e:
            errmsg = "'singularity' executable not found: " + Text(e)

        if errmsg:
            if req:
                raise WorkflowException(errmsg)
            else:
                return None

        if get_image(r, pull_image, dry_run):
            return os.path.abspath(r["dockerImageId"])
        else:
            if req:
                raise WorkflowException(u"Container image %s not found" % r["dockerImageId"])

    return None
