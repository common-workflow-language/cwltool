from __future__ import absolute_import
import logging
import os
import sys

if sys.version_info < (3, 4):
    from pathlib2 import Path
else:
    from pathlib import Path
from six.moves import urllib


_logger = logging.getLogger("cwltool")


def resolve_local(document_loader, uri):
    if uri.startswith("/"):
        path, frag = urllib.parse.urldefrag(uri)
        if os.path.exists(path):
            if frag:
                return "{}#{}".format(Path(path).as_uri(), frag)
            else:
                return Path(path).as_uri()
        else:
            return None
    if os.path.exists(urllib.parse.urlparse(
            urllib.parse.urldefrag(
                "{}/{}".format(Path.cwd().as_uri(), uri))[0])[2]):
        return "{}/{}".format(Path.cwd().as_uri(), uri)
    sharepaths = [os.environ.get("XDG_DATA_HOME", os.path.join(
        os.path.expanduser('~'), ".local", "share"))]
    sharepaths.extend(os.environ.get(
        "XDG_DATA_DIRS", "/usr/local/share/:/usr/share/").split(":"))
    shares = [os.path.join(s, "commonwl", uri) for s in sharepaths]

    _logger.debug("Search path is %s", shares)

    for path in shares:
        if os.path.exists(path):
            return Path(uri).as_uri()
        if os.path.exists("{}.cwl".format(path)):
            return Path("{}.cwl".format(path)).as_uri()
    return None


def tool_resolver(document_loader, uri):
    for r in [resolve_local, resolve_ga4gh_tool]:
        ret = r(document_loader, uri)
        if ret is not None:
            return ret


ga4gh_tool_registries = ["https://dockstore.org:8443"]

def resolve_ga4gh_tool(document_loader, uri):
    path, version = uri.partition(":")[::2]
    if not version:
        version = "latest"
    for reg in ga4gh_tool_registries:
        ds = "{0}/api/ga4gh/v1/tools/{1}/versions/{2}/plain-CWL/descriptor".format(reg, urllib.parse.quote(path, ""), urllib.parse.quote(version, ""))
        try:
            resp = document_loader.session.head(ds)
            resp.raise_for_status()
            return ds
        except Exception:
            pass
    return None
