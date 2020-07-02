from typing import Any

from ruamel import yaml
from schema_salad.avro.schema import Names

from cwltool import process, validate_js
from cwltool.sandboxjs import code_fragment_to_js

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
    test_cwl_yaml = yaml.main.round_trip_load(TEST_CWL)
    schema = process.get_schema("v1.0")[1]
    assert isinstance(schema, Names)
    clt_schema = schema.names["CommandLineTool"]

    exprs = validate_js.get_expressions(test_cwl_yaml, clt_schema)

    assert len(exprs) == 1


def test_validate_js_expressions(mocker: Any) -> None:
    test_cwl_yaml = yaml.main.round_trip_load(TEST_CWL)
    schema = process.get_schema("v1.0")[1]
    assert isinstance(schema, Names)
    clt_schema = schema.names["CommandLineTool"]

    mocker.patch("cwltool.validate_js._logger")
    # mocker.patch("cwltool.validate_js.print_js_hint_messages")
    validate_js.validate_js_expressions(test_cwl_yaml, clt_schema)

    validate_js._logger.warning.assert_called_with(" JSHINT: (function(){return ((kjdbfkjd));})()\n JSHINT:                      ^\n JSHINT: W117: 'kjdbfkjd' is not defined.")  # type: ignore


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
