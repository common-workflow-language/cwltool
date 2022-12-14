import pytest
from cwl_utils.sandboxjs import code_fragment_to_js
from schema_salad.avro.schema import Names
from schema_salad.utils import yaml_no_ts

from cwltool import process, validate_js

TEST_CWL = """
cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo

requirements:
  - class: InlineJavascriptRequirement
inputs:
  - id: parameter
    inputBinding:
      valueFrom: string before $(kjdbfkjd) string after
    type: string?

outputs: []
"""


def test_get_expressions() -> None:
    yaml = yaml_no_ts()
    test_cwl_yaml = yaml.load(TEST_CWL)
    schema = process.get_schema("v1.0")[1]
    assert isinstance(schema, Names)
    clt_schema = schema.names["org.w3id.cwl.cwl.CommandLineTool"]

    exprs = validate_js.get_expressions(test_cwl_yaml, clt_schema)

    assert len(exprs) == 1


def test_validate_js_expressions(caplog: pytest.LogCaptureFixture) -> None:
    """Test invalid JS expression."""
    yaml = yaml_no_ts()
    test_cwl_yaml = yaml.load(TEST_CWL)
    schema = process.get_schema("v1.0")[1]
    assert isinstance(schema, Names)
    clt_schema = schema.names["org.w3id.cwl.cwl.CommandLineTool"]

    validate_js.validate_js_expressions(test_cwl_yaml, clt_schema)

    assert (
        " JSHINT: (function(){return ((kjdbfkjd));})()\n"
        " JSHINT:                      ^\n"
        " JSHINT: W117: 'kjdbfkjd' is not defined."
    ) in caplog.text


def test_js_hint_basic() -> None:
    result = validate_js.jshint_js(
        """
    function funcName(){
    }
    """,
        [],
    )

    assert result.errors == []
    assert result.globals == ["funcName"]


def test_js_hint_reports_invalid_js() -> None:
    assert len(validate_js.jshint_js("<INVALID JS>").errors) > 1


def test_js_hint_warn_on_es6() -> None:
    assert (
        len(validate_js.jshint_js(code_fragment_to_js("((() => 4)())"), []).errors) == 1
    )


def test_js_hint_error_on_undefined_name() -> None:
    assert (
        len(validate_js.jshint_js(code_fragment_to_js("undefined_name()")).errors) == 1
    )


def test_js_hint_set_defined_name() -> None:
    assert (
        len(
            validate_js.jshint_js(
                code_fragment_to_js("defined_name()"), ["defined_name"]
            ).errors
        )
        == 0
    )
