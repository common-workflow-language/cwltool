"""Tests for cwltool.load_tool."""
import logging
from pathlib import Path

import pytest

from cwltool.context import LoadingContext, RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.load_tool import load_tool
from cwltool.loghandler import _logger, configure_logging
from cwltool.process import use_custom_schema, use_standard_schema
from cwltool.update import INTERNAL_VERSION
from cwltool.utils import CWLObjectType

from .util import get_data

configure_logging(_logger.handlers[-1], False, True, True, True)
_logger.setLevel(logging.DEBUG)


def test_check_version() -> None:
    """
    It is permitted to load without updating, but not execute.

    Attempting to execute without updating to the internal version should raise an error.
    """
    joborder = {"inp": "abc"}  # type: CWLObjectType
    loadingContext = LoadingContext({"do_update": True})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    for _ in tool.job(joborder, None, RuntimeContext()):
        pass

    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    with pytest.raises(WorkflowException):
        for _ in tool.job(joborder, None, RuntimeContext()):
            pass


def test_use_metadata() -> None:
    """Use the version from loadingContext.metadata if cwlVersion isn't present in the document."""
    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)

    loadingContext = LoadingContext()
    loadingContext.metadata = tool.metadata
    tooldata = tool.tool.copy()
    del tooldata["cwlVersion"]
    load_tool(tooldata, loadingContext)


def test_checklink_outputSource() -> None:
    """Is outputSource resolved correctly independent of value of do_validate."""
    outsrc = (
        Path(get_data("tests/wf/1st-workflow.cwl")).as_uri() + "#argument/classfile"
    )

    loadingContext = LoadingContext({"do_validate": True})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert tool.tool["outputs"][0]["outputSource"] == outsrc

    loadingContext = LoadingContext({"do_validate": False})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert tool.tool["outputs"][0]["outputSource"] == outsrc


def test_load_graph_fragment() -> None:
    """Reloading from a dictionary without a cwlVersion."""
    loadingContext = LoadingContext()
    uri = Path(get_data("tests/wf/scatter-wf4.cwl")).as_uri() + "#main"
    tool = load_tool(uri, loadingContext)

    loader = tool.doc_loader
    assert loader
    rs, metadata = loader.resolve_ref(uri)
    # Reload from a dict (in 'rs'), not a URI.  The dict is a fragment
    # of original document and doesn't have cwlVersion set, so test
    # that it correctly looks up the root document to get the
    # cwlVersion.
    assert isinstance(rs, str) or isinstance(rs, dict)
    tool = load_tool(rs, loadingContext)
    assert tool.metadata["cwlVersion"] == INTERNAL_VERSION


def test_load_graph_fragment_from_packed() -> None:
    """Loading a fragment from packed with update."""
    loadingContext = LoadingContext()
    uri = Path(get_data("tests/wf/packed-with-loadlisting.cwl")).as_uri() + "#main"
    try:
        with open(get_data("cwltool/extensions.yml")) as res:
            use_custom_schema("v1.0", "http://commonwl.org/cwltool", res.read())

        # The updater transforms LoadListingRequirement from an
        # extension (in v1.0) to a core feature (in v1.1) but there
        # was a bug when loading a packed workflow and loading a
        # specific fragment it would get the un-updated document.
        # This recreates that case and asserts that we are using the
        # updated document like we should.

        tool = load_tool(uri, loadingContext)

        assert tool.tool["requirements"] == [
            {"class": "LoadListingRequirement", "loadListing": "no_listing"}
        ]

        # This tests an additional, related bug, in which the updater
        # updates only one fragment of the document, but would update
        # the metadata dict in-place.  This had the effect of marking
        # the original document as updated.  On a subsequent load, it
        # would get the original un-updated document, which mistakenly
        # had the version modified in place, and validate it with the
        # newer schema instead of the original one.
        #
        # The specific case where this failed was
        # cwltool:LoadListingRequirement which is only recognized for
        # v1.0 documents, newer documents are supposed to be
        # auto-updated to the spec LoadListingRequirement, so it is
        # dropped from the schema.  However if we try to validate a
        # v1.0 document with a v1.2 schema, it will throw an error the
        # cwltool:LoadListingRequirement extension.
        #
        # This was solved by making a shallow copy of the metadata
        # dict to ensure that the updater did not modify the original
        # document.
        uri2 = (
            Path(get_data("tests/wf/packed-with-loadlisting.cwl")).as_uri()
            + "#16169-step.cwl"
        )
        tool2 = load_tool(uri2, loadingContext)

    finally:
        use_standard_schema("v1.0")
