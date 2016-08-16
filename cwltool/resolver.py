import os
import logging
import urllib
import urlparse

_logger = logging.getLogger("cwltool")

def resolve_local(document_loader, uri):
    if uri.startswith("/"):
        return None
    shares = [os.environ.get("XDG_DATA_HOME", os.path.join(os.environ["HOME"], ".local", "share"))]
    shares.extend(os.environ.get("XDG_DATA_DIRS", "/usr/local/share/:/usr/share/").split(":"))
    shares = [os.path.join(s, "commonwl", uri) for s in shares]
    shares.insert(0, os.path.join(os.getcwd(), uri))

    _logger.debug("Search path is %s", shares)

    for s in shares:
        if os.path.exists(s):
            return ("file://%s" % s)
        if os.path.exists("%s.cwl" % s):
            return ("file://%s.cwl" % s)
    return None

def resolve_ga4gh_tool(document_loader, uri):
    ds = "https://staging.dockstore.org:8443/api/ga4gh/v1/tools/%s/versions/master/plain-CWL/descriptor" % urllib.quote(uri, "")
    print ds
    try:
        resp = document_loader.session.head(ds)
        resp.raise_for_status()
        return ds
    except Exception:
        pass
    return None

def tool_resolver(document_loader, uri):
    for r in [resolve_local, resolve_ga4gh_tool]:
        ret = r(document_loader, uri)
        if ret is not None:
            return ret
    return uri
