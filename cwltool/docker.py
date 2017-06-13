from __future__ import absolute_import
import logging
import os
import re
import subprocess
import sys
import tempfile
from typing import Text

import requests

from .errors import WorkflowException

_logger = logging.getLogger("cwltool")


def get_image(dockerRequirement, pull_image, dry_run=False):
    # type: (Dict[Text, Text], bool, bool) -> bool
    found = False

    if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
        dockerRequirement["dockerImageId"] = dockerRequirement["dockerPull"]

    for ln in subprocess.check_output(
            ["docker", "images", "--no-trunc", "--all"]).splitlines():
        try:
            m = re.match(r"^([^ ]+)\s+([^ ]+)\s+([^ ]+)", ln)
            sp = dockerRequirement["dockerImageId"].split(":")
            if len(sp) == 1:
                sp.append("latest")
            elif len(sp) == 2:
                #  if sp[1] doesn't  match valid tag names, it is a part of repository
                if not re.match(r'[\w][\w.-]{0,127}', sp[1]):
                    sp[0] = sp[0] + ":" + sp[1]
                    sp[1] = "latest"
            elif len(sp) == 3:
                if re.match(r'[\w][\w.-]{0,127}', sp[2]):
                    sp[0] = sp[0] + ":" + sp[1]
                    sp[1] = sp[2]
                    del sp[2]

            # check for repository:tag match or image id match
            if ((sp[0] == m.group(1) and sp[1] == m.group(2)) or dockerRequirement["dockerImageId"] == m.group(3)):
                found = True
                break
        except ValueError:
            pass

    if not found and pull_image:
        cmd = []  # type: List[str]
        if "dockerPull" in dockerRequirement:
            cmd = ["docker", "pull", str(dockerRequirement["dockerPull"])]
            _logger.info(Text(cmd))
            if not dry_run:
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True
        elif "dockerFile" in dockerRequirement:
            dockerfile_dir = str(tempfile.mkdtemp())
            with open(os.path.join(dockerfile_dir, "Dockerfile"), "w") as df:
                df.write(dockerRequirement["dockerFile"])
            cmd = ["docker", "build", "--tag=%s" %
                   str(dockerRequirement["dockerImageId"]), dockerfile_dir]
            _logger.info(Text(cmd))
            if not dry_run:
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True
        elif "dockerLoad" in dockerRequirement:
            cmd = ["docker", "load"]
            _logger.info(Text(cmd))
            if not dry_run:
                if os.path.exists(dockerRequirement["dockerLoad"]):
                    _logger.info(u"Loading docker image from %s", dockerRequirement["dockerLoad"])
                    with open(dockerRequirement["dockerLoad"], "rb") as f:
                        loadproc = subprocess.Popen(cmd, stdin=f, stdout=sys.stderr)
                else:
                    loadproc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=sys.stderr)
                    _logger.info(u"Sending GET request to %s", dockerRequirement["dockerLoad"])
                    req = requests.get(dockerRequirement["dockerLoad"], stream=True)
                    n = 0
                    for chunk in req.iter_content(1024 * 1024):
                        n += len(chunk)
                        _logger.info("\r%i bytes" % (n))
                        loadproc.stdin.write(chunk)
                    loadproc.stdin.close()
                rcode = loadproc.wait()
                if rcode != 0:
                    raise WorkflowException("Docker load returned non-zero exit status %i" % (rcode))
                found = True
        elif "dockerImport" in dockerRequirement:
            cmd = ["docker", "import", str(dockerRequirement["dockerImport"]),
                   str(dockerRequirement["dockerImageId"])]
            _logger.info(Text(cmd))
            if not dry_run:
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True

    return found


def get_from_requirements(r, req, pull_image, dry_run=False):
    # type: (Dict[Text, Text], bool, bool, bool) -> Text
    if r:
        errmsg = None
        try:
            subprocess.check_output(["docker", "version"])
        except subprocess.CalledProcessError as e:
            errmsg = "Cannot communicate with docker daemon: " + Text(e)
        except OSError as e:
            errmsg = "'docker' executable not found: " + Text(e)

        if errmsg:
            if req:
                raise WorkflowException(errmsg)
            else:
                return None

        if get_image(r, pull_image, dry_run):
            return r["dockerImageId"]
        else:
            if req:
                raise WorkflowException(u"Docker image %s not found" % r["dockerImageId"])

    return None
