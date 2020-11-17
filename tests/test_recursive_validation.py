from cwltool.load_tool import fetch_document, recursive_resolve_and_validate_document

from .util import get_data


def test_recursive_validation() -> None:
    loadingContext, workflowobj, uri = fetch_document(
        get_data("tests/wf/default_path.cwl")
    )
    loadingContext, uri, tool = recursive_resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )
