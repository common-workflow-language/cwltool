"""Resolves references to CWL documents from local or remote places."""

import os
import urllib
from pathlib import Path
from typing import Optional

from schema_salad.ref_resolver import Loader

from .loghandler import _logger


def resolve_local(document_loader: Optional[Loader], uri: str) -> Optional[str]:
    pathpart, frag = urllib.parse.urldefrag(uri)

    try:
        pathobj = Path(pathpart).resolve()
    except OSError:
        _logger.debug("local resolver could not resolve %s", uri)
        return None

    if pathobj.is_file():
        if frag:
            return f"{pathobj.as_uri()}#{frag}"
        return pathobj.as_uri()

    sharepaths = [
        os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share"))
    ]
    sharepaths.extend(os.environ.get("XDG_DATA_DIRS", "/usr/local/share/:/usr/share/").split(":"))
    shares = [os.path.join(s, "commonwl", uri) for s in sharepaths]

    _logger.debug("Search path is %s", shares)

    for path in shares:
        if os.path.exists(path):
            return Path(uri).as_uri()
        if os.path.exists(f"{path}.cwl"):
            return Path(f"{path}.cwl").as_uri()
    return None


def tool_resolver(document_loader: Loader, uri: str) -> Optional[str]:
    for r in [resolve_local, resolve_ga4gh_tool]:
        ret = r(document_loader, uri)
        if ret is not None:
            return ret
    return None


ga4gh_tool_registries = ["https://dockstore.org/api"]
# in the TRS registry, a primary descriptor can be reached at
# {0}/api/ga4gh/v2/tools/{1}/versions/{2}/plain-CWL/descriptor
# The primary descriptor is a CommandLineTool in the case that the files
# endpoint only describes one file
# When the primary descriptor is a Workflow, files need to be imported without
# stripping off "descriptor", looking at the files endpoint is a workaround
# tested with TRS version 2.0.0-beta.2
# TODO not stripping off "descriptor" when looking for local imports would also
# work https://github.com/ga4gh/tool-registry-service-schemas/blob/2.0.0-beta.2/src/main/resources/swagger/ga4gh-tool-discovery.yaml#L273  # noqa: B950
GA4GH_TRS_FILES = "{0}/api/ga4gh/v2/tools/{1}/versions/{2}/CWL/files"
GA4GH_TRS_PRIMARY_DESCRIPTOR = "{0}/api/ga4gh/v2/tools/{1}/versions/{2}/plain-CWL/descriptor/{3}"


def resolve_ga4gh_tool(document_loader: Loader, uri: str) -> Optional[str]:
    path, version = uri.partition(":")[::2]
    if not version:
        version = "latest"
    for reg in ga4gh_tool_registries:
        ds = GA4GH_TRS_FILES.format(
            reg, urllib.parse.quote(path, ""), urllib.parse.quote(version, "")
        )
        try:
            _logger.debug("Head path is %s", ds)
            resp = document_loader.session.head(ds)
            resp.raise_for_status()

            _logger.debug("Passed head path of %s", ds)

            resp = document_loader.session.get(ds)
            for file_listing in resp.json():
                if file_listing.get("file_type") == "PRIMARY_DESCRIPTOR":
                    primary_path = file_listing.get("path")
                    ds2 = GA4GH_TRS_PRIMARY_DESCRIPTOR.format(
                        reg,
                        urllib.parse.quote(path, ""),
                        urllib.parse.quote(version, ""),
                        urllib.parse.quote(primary_path, ""),
                    )
                    _logger.debug("Resolved %s", ds2)
                    return ds2
        except Exception:  # nosec
            pass
    return None
