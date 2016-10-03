import logging
import os

from schema_salad.ref_resolver import file_uri

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
            return file_uri(s)
        if os.path.exists("%s.cwl" % s):
            return file_uri(s)
    return None


def tool_resolver(document_loader, uri):
    for r in [resolve_local, resolve_ga4gh_tool]:
        ret = r(document_loader, uri)
        if ret is not None:
            return ret
    return file_uri(os.path.abspath(uri), split_frag=True)


def resolve_ga4gh_tool(document_loader, uri):
    path, version = uri.partition(":")[::2]
    if not version:
        version = "latest"
    ds = "https://dockstore.org:8443/api/ga4gh/v1/tools/{0}/versions/{1}/plain-CWL/descriptor".format(urllib.quote(path, ""), urllib.quote(version, ""))
    try:
        resp = document_loader.session.head(ds)
        resp.raise_for_status()
        return ds
    except Exception:
        pass
    return None
