from schema_salad.ref_resolver import Loader

from cwltool.load_tool import fetch_document, validate_document

from .util import get_data


def test_default_path():
    """Testing that error is not raised when default path is not present"""
    document_loader, workflowobj, uri = fetch_document(
        get_data("tests/wf/default_path.cwl"))
    document_loader, _, processobj, _, uri = validate_document(
        document_loader, workflowobj, uri)

    assert isinstance(document_loader, Loader)
    assert "cwlVersion" in processobj
