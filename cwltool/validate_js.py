import copy
import itertools
import json
import logging
from collections import namedtuple
from typing import (
    Any,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)

from pkg_resources import resource_stream

from ruamel.yaml.comments import CommentedMap
from schema_salad import avro
from schema_salad.sourceline import SourceLine
from schema_salad.utils import json_dumps
from schema_salad.validate import Schema, validate_ex

from .errors import WorkflowException
from .expression import SubstitutionError
from .expression import scanner as scan_expression
from .loghandler import _logger
from .sandboxjs import code_fragment_to_js, exec_js_process


def is_expression(tool, schema):
    # type: (Any, Optional[Schema]) -> bool
    return (
        isinstance(schema, avro.schema.EnumSchema)
        and schema.name == "Expression"
        and isinstance(tool, str)
    )


class SuppressLog(logging.Filter):
    def __init__(self, name):  # type: (str) -> None
        """Initialize this log suppressor."""
        name = str(name)
        super(SuppressLog, self).__init__(name)

    def filter(self, record):  # type: (logging.LogRecord) -> bool
        return False


_logger_validation_warnings = logging.getLogger("cwltool.validation_warnings")
_logger_validation_warnings.addFilter(SuppressLog("cwltool.validation_warnings"))


def get_expressions(
    tool: Union[CommentedMap, str],
    schema: Optional[Union[avro.schema.Schema, avro.schema.ArraySchema]],
    source_line: Optional[SourceLine] = None,
) -> List[Tuple[str, Optional[SourceLine]]]:
    if is_expression(tool, schema):
        return [(cast(str, tool), source_line)]
    elif isinstance(schema, avro.schema.UnionSchema):
        valid_schema = None

        for possible_schema in schema.schemas:
            if is_expression(tool, possible_schema):
                return [(cast(str, tool), source_line)]
            elif validate_ex(
                possible_schema,
                tool,
                raise_ex=False,
                logger=_logger_validation_warnings,
            ):
                valid_schema = possible_schema

        return get_expressions(tool, valid_schema, source_line)
    elif isinstance(schema, avro.schema.ArraySchema):
        if not isinstance(tool, MutableSequence):
            return []

        return list(
            itertools.chain(
                *map(
                    lambda x: get_expressions(
                        x[1], schema.items, SourceLine(tool, x[0])  # type: ignore
                    ),
                    enumerate(tool),
                )
            )
        )

    elif isinstance(schema, avro.schema.RecordSchema):
        if not isinstance(tool, MutableMapping):
            return []

        expression_nodes = []

        for schema_field in schema.fields:
            if schema_field.name in tool:
                expression_nodes.extend(
                    get_expressions(
                        tool[schema_field.name],
                        schema_field.type,
                        SourceLine(tool, schema_field.name),
                    )
                )

        return expression_nodes
    else:
        return []


JSHintJSReturn = namedtuple("jshint_return", ["errors", "globals"])


def jshint_js(
    js_text: str,
    globals: Optional[List[str]] = None,
    options: Optional[Dict[str, Union[List[str], str, int]]] = None,
) -> Tuple[List[str], List[str]]:
    if globals is None:
        globals = []
    if options is None:
        options = {
            "includewarnings": [
                "W117",  # <VARIABLE> not defined
                "W104",
                "W119",  # using ES6 features
            ],
            "strict": "implied",
            "esversion": 5,
        }

    with resource_stream(__name__, "jshint/jshint.js") as file:
        # NOTE: we need a global variable for lodash (which jshint depends on)
        jshint_functions_text = "var global = this;" + file.read().decode("utf-8")

    with resource_stream(__name__, "jshint/jshint_wrapper.js") as file:
        # NOTE: we need to assign to ob, as the expression {validateJS: validateJS} as an expression
        # is interpreted as a block with a label `validateJS`
        jshint_functions_text += (
            "\n"
            + file.read().decode("utf-8")
            + "\nvar ob = {validateJS: validateJS}; ob"
        )

    returncode, stdout, stderr = exec_js_process(
        "validateJS(%s)"
        % json_dumps({"code": js_text, "options": options, "globals": globals}),
        timeout=30,
        context=jshint_functions_text,
    )

    def dump_jshint_error():
        # type: () -> None
        raise RuntimeError(
            'jshint failed to run succesfully\nreturncode: %d\nstdout: "%s"\nstderr: "%s"'
            % (returncode, stdout, stderr)
        )

    if returncode == -1:
        _logger.warning("jshint process timed out")

    if returncode != 0:
        dump_jshint_error()

    try:
        jshint_json = json.loads(stdout)
    except ValueError:
        dump_jshint_error()

    jshint_errors = []  # type: List[str]

    js_text_lines = js_text.split("\n")

    for jshint_error_obj in jshint_json.get("errors", []):
        text = "JSHINT: " + js_text_lines[jshint_error_obj["line"] - 1] + "\n"
        text += "JSHINT: " + " " * (jshint_error_obj["character"] - 1) + "^\n"
        text += "JSHINT: %s: %s" % (
            jshint_error_obj["code"],
            jshint_error_obj["reason"],
        )
        jshint_errors.append(text)

    return JSHintJSReturn(jshint_errors, jshint_json.get("globals", []))


def print_js_hint_messages(js_hint_messages, source_line):
    # type: (List[str], Optional[SourceLine]) -> None
    if source_line is not None:
        for js_hint_message in js_hint_messages:
            _logger.warning(source_line.makeError(js_hint_message))


def validate_js_expressions(
    tool: CommentedMap,
    schema: Schema,
    jshint_options: Optional[Dict[str, Union[List[str], str, int]]] = None,
) -> None:

    if tool.get("requirements") is None:
        return

    requirements = tool["requirements"]

    default_globals = ["self", "inputs", "runtime", "console"]

    for prop in reversed(requirements):
        if prop["class"] == "InlineJavascriptRequirement":
            expression_lib = prop.get("expressionLib", [])
            break
    else:
        return

    js_globals = copy.deepcopy(default_globals)

    for i, expression_lib_line in enumerate(expression_lib):
        expression_lib_line_errors, expression_lib_line_globals = jshint_js(
            expression_lib_line, js_globals, jshint_options
        )
        js_globals.extend(expression_lib_line_globals)
        print_js_hint_messages(
            expression_lib_line_errors, SourceLine(expression_lib, i)
        )

    expressions = get_expressions(tool, schema)

    for expression, source_line in expressions:
        unscanned_str = expression.strip()
        try:
            scan_slice = scan_expression(unscanned_str)
        except SubstitutionError as se:
            if source_line:
                source_line.raise_type = WorkflowException
                raise source_line.makeError(str(se))
            else:
                raise se

        while scan_slice:
            if unscanned_str[scan_slice[0]] == "$":
                code_fragment = unscanned_str[scan_slice[0] + 1 : scan_slice[1]]
                code_fragment_js = code_fragment_to_js(code_fragment, "")
                expression_errors, _ = jshint_js(
                    code_fragment_js, js_globals, jshint_options
                )
                print_js_hint_messages(expression_errors, source_line)

            unscanned_str = unscanned_str[scan_slice[1] :]
            scan_slice = scan_expression(unscanned_str)
