from cwltool.load_tool import fetch_document, resolve_and_validate_document

from .util import get_data


def test_default_path() -> None:
    """Error is not raised when default path is not present."""
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/default_path.cwl")
    )
    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
    loader = loadingContext.loader
    assert loader
    processobj = loader.resolve_ref(uri)[0]
    assert isinstance(processobj, dict)

    assert "cwlVersion" in processobj
