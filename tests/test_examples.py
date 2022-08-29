import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Union, cast

import cwl_utils.expression as expr
import pydot
import pytest
from cwl_utils.errors import JavascriptException
from cwl_utils.sandboxjs import param_re
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.exceptions import ValidationException

import cwltool.checker
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from cwltool.checker import can_assign_src_to_sink
from cwltool.context import RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.main import main
from cwltool.process import CWL_IANA
from cwltool.utils import CWLObjectType, dedup

from .util import get_data, get_main_output, needs_docker, working_directory

sys.argv = [""]

expression_match = [
    ("(foo)", True),
    ("(foo.bar)", True),
    ("(foo['bar'])", True),
    ('(foo["bar"])', True),
    ("(foo.bar.baz)", True),
    ("(foo['bar'].baz)", True),
    ("(foo['bar']['baz'])", True),
    ("(foo['b\\'ar']['baz'])", True),
    ("(foo['b ar']['baz'])", True),
    ("(foo_bar)", True),
    ('(foo.["bar"])', False),
    ('(.foo["bar"])', False),
    ('(foo ["bar"])', False),
    ('( foo["bar"])', False),
    ("(foo[bar].baz)", False),
    ("(foo['bar\"].baz)", False),
    ("(foo['bar].baz)", False),
    ("{foo}", False),
    ("(foo.bar", False),
    ("foo.bar)", False),
    ("foo.b ar)", False),
    ("foo.b'ar)", False),
    ("(foo+bar", False),
    ("(foo bar", False),
]


@pytest.mark.parametrize("expression,expected", expression_match)
def test_expression_match(expression: str, expected: bool) -> None:
    match = param_re.match(expression)
    assert (match is not None) == expected


interpolate_input = {
    "foo": {
        "bar": {"baz": "zab1"},
        "b ar": {"baz": 2},
        "b'ar": {"baz": True},
        'b"ar': {"baz": None},
    },
    "lst": ["A", "B"],
}  # type: Dict[str, Any]

interpolate_parameters = [
    ("$(foo)", interpolate_input["foo"]),
    ("$(foo.bar)", interpolate_input["foo"]["bar"]),
    ("$(foo['bar'])", interpolate_input["foo"]["bar"]),
    ('$(foo["bar"])', interpolate_input["foo"]["bar"]),
    ("$(foo.bar.baz)", interpolate_input["foo"]["bar"]["baz"]),
    ("$(foo['bar'].baz)", interpolate_input["foo"]["bar"]["baz"]),
    ("$(foo['bar'][\"baz\"])", interpolate_input["foo"]["bar"]["baz"]),
    ("$(foo.bar['baz'])", interpolate_input["foo"]["bar"]["baz"]),
    ("$(foo['b\\'ar'].baz)", True),
    ('$(foo["b\'ar"].baz)', True),
    ("$(foo['b\\\"ar'].baz)", None),
    ("$(lst[0])", "A"),
    ("$(lst[1])", "B"),
    ("$(lst.length)", 2),
    ("$(lst['length'])", 2),
    ("-$(foo.bar)", """-{"baz": "zab1"}"""),
    ("-$(foo['bar'])", """-{"baz": "zab1"}"""),
    ('-$(foo["bar"])', """-{"baz": "zab1"}"""),
    ("-$(foo.bar.baz)", "-zab1"),
    ("-$(foo['bar'].baz)", "-zab1"),
    ("-$(foo['bar'][\"baz\"])", "-zab1"),
    ("-$(foo.bar['baz'])", "-zab1"),
    ("-$(foo['b ar'].baz)", "-2"),
    ("-$(foo['b\\'ar'].baz)", "-true"),
    ('-$(foo["b\\\'ar"].baz)', "-true"),
    ("-$(foo['b\\\"ar'].baz)", "-null"),
    ("$(foo.bar) $(foo.bar)", """{"baz": "zab1"} {"baz": "zab1"}"""),
    ("$(foo['bar']) $(foo['bar'])", """{"baz": "zab1"} {"baz": "zab1"}"""),
    ('$(foo["bar"]) $(foo["bar"])', """{"baz": "zab1"} {"baz": "zab1"}"""),
    ("$(foo.bar.baz) $(foo.bar.baz)", "zab1 zab1"),
    ("$(foo['bar'].baz) $(foo['bar'].baz)", "zab1 zab1"),
    ("$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])", "zab1 zab1"),
    ("$(foo.bar['baz']) $(foo.bar['baz'])", "zab1 zab1"),
    ("$(foo['b ar'].baz) $(foo['b ar'].baz)", "2 2"),
    ("$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", "true true"),
    ('$(foo["b\\\'ar"].baz) $(foo["b\\\'ar"].baz)', "true true"),
    ("$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", "null null"),
]


@pytest.mark.parametrize("pattern,expected", interpolate_parameters)
def test_expression_interpolate(pattern: str, expected: Any) -> None:
    assert expr.interpolate(pattern, interpolate_input) == expected


parameter_to_expressions = [
    (
        "-$(foo)",
        r"""-{"bar":{"baz":"zab1"},"b ar":{"baz":2},"b'ar":{"baz":true},"b\"ar":{"baz":null}}""",
    ),
    ("-$(foo.bar)", """-{"baz":"zab1"}"""),
    ("-$(foo['bar'])", """-{"baz":"zab1"}"""),
    ('-$(foo["bar"])', """-{"baz":"zab1"}"""),
    ("-$(foo.bar.baz)", "-zab1"),
    ("-$(foo['bar'].baz)", "-zab1"),
    ("-$(foo['bar'][\"baz\"])", "-zab1"),
    ("-$(foo.bar['baz'])", "-zab1"),
    ("-$(foo['b ar'].baz)", "-2"),
    ("-$(foo['b\\'ar'].baz)", "-true"),
    ('-$(foo["b\\\'ar"].baz)', "-true"),
    ("-$(foo['b\\\"ar'].baz)", "-null"),
    ("$(foo.bar) $(foo.bar)", """{"baz":"zab1"} {"baz":"zab1"}"""),
    ("$(foo['bar']) $(foo['bar'])", """{"baz":"zab1"} {"baz":"zab1"}"""),
    ('$(foo["bar"]) $(foo["bar"])', """{"baz":"zab1"} {"baz":"zab1"}"""),
    ("$(foo.bar.baz) $(foo.bar.baz)", "zab1 zab1"),
    ("$(foo['bar'].baz) $(foo['bar'].baz)", "zab1 zab1"),
    ("$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])", "zab1 zab1"),
    ("$(foo.bar['baz']) $(foo.bar['baz'])", "zab1 zab1"),
    ("$(foo['b ar'].baz) $(foo['b ar'].baz)", "2 2"),
    ("$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", "true true"),
    ('$(foo["b\\\'ar"].baz) $(foo["b\\\'ar"].baz)', "true true"),
    ("$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", "null null"),
]


@pytest.mark.parametrize("pattern,expected", parameter_to_expressions)
def test_parameter_to_expression(pattern: str, expected: Any) -> None:
    """Test the interpolate convert_to_expression feature."""
    expression = expr.interpolate(pattern, {}, convert_to_expression=True)
    assert isinstance(expression, str)
    assert (
        expr.interpolate(
            expression,
            {},
            jslib=expr.jshead([], interpolate_input),
            fullJS=True,
            debug=True,
        )
        == expected
    )


param_to_expr_interpolate_escapebehavior = (
    ("\\$(foo.bar.baz)", "$(foo.bar.baz)", 1),
    ("\\\\$(foo.bar.baz)", "\\zab1", 1),
    ("\\\\\\$(foo.bar.baz)", "\\$(foo.bar.baz)", 1),
    ("\\\\\\\\$(foo.bar.baz)", "\\\\zab1", 1),
    ("\\$foo", "$foo", 1),
    ("\\foo", "foo", 1),
    ("\\x", "x", 1),
    ("\\\\x", "\\x", 1),
    ("\\\\\\x", "\\x", 1),
    ("\\\\\\\\x", "\\\\x", 1),
    ("\\$(foo.bar.baz)", "$(foo.bar.baz)", 2),
    ("\\\\$(foo.bar.baz)", "\\zab1", 2),
    ("\\\\\\$(foo.bar.baz)", "\\$(foo.bar.baz)", 2),
    ("\\\\\\\\$(foo.bar.baz)", "\\\\zab1", 2),
    ("\\$foo", "\\$foo", 2),
    ("\\foo", "\\foo", 2),
    ("\\x", "\\x", 2),
    ("\\\\x", "\\x", 2),
    ("\\\\\\x", "\\\\x", 2),
    ("\\\\\\\\x", "\\\\x", 2),
)


@pytest.mark.parametrize(
    "pattern,expected,behavior", param_to_expr_interpolate_escapebehavior
)
def test_parameter_to_expression_interpolate_escapebehavior(
    pattern: str, expected: str, behavior: int
) -> None:
    """Test escaping behavior in an convert_to_expression context."""
    expression = expr.interpolate(
        pattern, {}, escaping_behavior=behavior, convert_to_expression=True
    )
    assert isinstance(expression, str)
    assert (
        expr.interpolate(
            expression,
            {},
            jslib=expr.jshead([], interpolate_input),
            fullJS=True,
            debug=True,
        )
        == expected
    )


interpolate_bad_parameters = [
    ("$(fooz)"),
    ("$(foo.barz)"),
    ("$(foo['barz'])"),
    ('$(foo["barz"])'),
    ("$(foo.bar.bazz)"),
    ("$(foo['bar'].bazz)"),
    ("$(foo['bar'][\"bazz\"])"),
    ("$(foo.bar['bazz'])"),
    ("$(foo['b\\'ar'].bazz)"),
    ('$(foo["b\'ar"].bazz)'),
    ("$(foo['b\\\"ar'].bazz)"),
    ("$(lst[O])"),  # not "0" the number, but the letter O
    ("$(lst[2])"),
    ("$(lst.lengthz)"),
    ("$(lst['lengthz'])"),
    ("-$(foo.barz)"),
    ("-$(foo['barz'])"),
    ('-$(foo["barz"])'),
    ("-$(foo.bar.bazz)"),
    ("-$(foo['bar'].bazz)"),
    ("-$(foo['bar'][\"bazz\"])"),
    ("-$(foo.bar['bazz'])"),
    ("-$(foo['b ar'].bazz)"),
    ("-$(foo['b\\'ar'].bazz)"),
    ('-$(foo["b\\\'ar"].bazz)'),
    ("-$(foo['b\\\"ar'].bazz)"),
]


@pytest.mark.parametrize("pattern", interpolate_bad_parameters)
def test_expression_interpolate_failures(pattern: str) -> None:
    result = None
    with pytest.raises(JavascriptException):
        result = expr.interpolate(pattern, interpolate_input)


interpolate_escapebehavior = (
    ("\\$(foo.bar.baz)", "$(foo.bar.baz)", 1),
    ("\\\\$(foo.bar.baz)", "\\zab1", 1),
    ("\\\\\\$(foo.bar.baz)", "\\$(foo.bar.baz)", 1),
    ("\\\\\\\\$(foo.bar.baz)", "\\\\zab1", 1),
    ("\\$foo", "$foo", 1),
    ("\\foo", "foo", 1),
    ("\\x", "x", 1),
    ("\\\\x", "\\x", 1),
    ("\\\\\\x", "\\x", 1),
    ("\\\\\\\\x", "\\\\x", 1),
    ("\\$(foo.bar.baz)", "$(foo.bar.baz)", 2),
    ("\\\\$(foo.bar.baz)", "\\zab1", 2),
    ("\\\\\\$(foo.bar.baz)", "\\$(foo.bar.baz)", 2),
    ("\\\\\\\\$(foo.bar.baz)", "\\\\zab1", 2),
    ("\\$foo", "\\$foo", 2),
    ("\\foo", "\\foo", 2),
    ("\\x", "\\x", 2),
    ("\\\\x", "\\x", 2),
    ("\\\\\\x", "\\\\x", 2),
    ("\\\\\\\\x", "\\\\x", 2),
)


@pytest.mark.parametrize("pattern,expected,behavior", interpolate_escapebehavior)
def test_expression_interpolate_escapebehavior(
    pattern: str, expected: str, behavior: int
) -> None:
    """Test escaping behavior in an interpolation context."""
    assert (
        expr.interpolate(pattern, interpolate_input, escaping_behavior=behavior)
        == expected
    )


def test_factory() -> None:
    factory = cwltool.factory.Factory()
    echo = factory.make(get_data("tests/echo.cwl"))

    assert echo(inp="foo") == {"out": "foo\n"}


def test_factory_bad_outputs() -> None:
    factory = cwltool.factory.Factory()

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/echo_broken_outputs.cwl"))


def test_factory_default_args() -> None:
    factory = cwltool.factory.Factory()

    assert factory.runtime_context.use_container is True
    assert factory.runtime_context.on_error == "stop"


def test_factory_redefined_args() -> None:
    runtime_context = RuntimeContext()
    runtime_context.use_container = False
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    assert factory.runtime_context.use_container is False
    assert factory.runtime_context.on_error == "continue"


def test_factory_partial_scatter() -> None:
    runtime_context = RuntimeContext()
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    with pytest.raises(cwltool.factory.WorkflowStatus) as err_info:
        factory.make(get_data("tests/wf/scatterfail.cwl"))()

    result = err_info.value.out
    assert isinstance(result, dict)
    assert (
        result["out"][0]["checksum"] == "sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    )
    assert result["out"][1] is None
    assert (
        result["out"][2]["checksum"] == "sha1$a3db5c13ff90a36963278c6a39e4ee3c22e2a436"
    )


def test_factory_partial_output() -> None:
    runtime_context = RuntimeContext()
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    with pytest.raises(cwltool.factory.WorkflowStatus) as err_info:
        factory.make(get_data("tests/wf/wffail.cwl"))()

    result = err_info.value.out
    assert isinstance(result, dict)
    assert result["out1"]["checksum"] == "sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e"
    assert result["out2"] is None


def test_scandeps() -> None:
    obj: CWLObjectType = {
        "id": "file:///example/foo.cwl",
        "steps": [
            {
                "id": "file:///example/foo.cwl#step1",
                "inputs": [
                    {
                        "id": "file:///example/foo.cwl#input1",
                        "default": {
                            "class": "File",
                            "location": "file:///example/data.txt",
                        },
                    }
                ],
                "run": {
                    "id": "file:///example/bar.cwl",
                    "inputs": [
                        {
                            "id": "file:///example/bar.cwl#input2",
                            "default": {
                                "class": "Directory",
                                "location": "file:///example/data2",
                                "listing": [
                                    {
                                        "class": "File",
                                        "location": "file:///example/data3.txt",
                                        "secondaryFiles": [
                                            {
                                                "class": "File",
                                                "location": "file:///example/data5.txt",
                                            }
                                        ],
                                    }
                                ],
                            },
                        },
                        {
                            "id": "file:///example/bar.cwl#input3",
                            "default": {
                                "class": "Directory",
                                "listing": [
                                    {
                                        "class": "File",
                                        "location": "file:///example/data4.txt",
                                    }
                                ],
                            },
                        },
                        {
                            "id": "file:///example/bar.cwl#input4",
                            "default": {"class": "File", "contents": "file literal"},
                        },
                    ],
                },
            }
        ],
    }

    def loadref(
        base: str, p: Union[CommentedMap, CommentedSeq, str, None]
    ) -> Union[CommentedMap, CommentedSeq, str, None]:
        if isinstance(p, dict):
            return p
        raise Exception("test case can't load things")

    scanned_deps = cast(
        List[Dict[str, Any]],
        cwltool.process.scandeps(
            cast(str, obj["id"]),
            obj,
            {"$import", "run"},
            {"$include", "$schemas", "location"},
            loadref,
        ),
    )

    scanned_deps.sort(key=lambda k: cast(str, k["basename"]))

    expected_deps = [
        {
            "basename": "bar.cwl",
            "nameroot": "bar",
            "class": "File",
            "format": CWL_IANA,
            "nameext": ".cwl",
            "location": "file:///example/bar.cwl",
        },
        {
            "basename": "data.txt",
            "nameroot": "data",
            "class": "File",
            "nameext": ".txt",
            "location": "file:///example/data.txt",
        },
        {
            "basename": "data2",
            "class": "Directory",
            "location": "file:///example/data2",
            "listing": [
                {
                    "basename": "data3.txt",
                    "nameroot": "data3",
                    "class": "File",
                    "nameext": ".txt",
                    "location": "file:///example/data3.txt",
                    "secondaryFiles": [
                        {
                            "class": "File",
                            "basename": "data5.txt",
                            "location": "file:///example/data5.txt",
                            "nameext": ".txt",
                            "nameroot": "data5",
                        }
                    ],
                }
            ],
        },
        {
            "basename": "data4.txt",
            "nameroot": "data4",
            "class": "File",
            "nameext": ".txt",
            "location": "file:///example/data4.txt",
        },
    ]

    assert scanned_deps == expected_deps

    scanned_deps2 = cast(
        List[Dict[str, Any]],
        cwltool.process.scandeps(
            cast(str, obj["id"]),
            obj,
            set(
                ("run"),
            ),
            set(),
            loadref,
        ),
    )

    scanned_deps2.sort(key=lambda k: cast(str, k["basename"]))

    expected_deps = [
        {
            "basename": "bar.cwl",
            "nameroot": "bar",
            "format": CWL_IANA,
            "class": "File",
            "nameext": ".cwl",
            "location": "file:///example/bar.cwl",
        }
    ]

    assert scanned_deps2 == expected_deps


def test_scandeps_samedirname() -> None:
    obj: CWLObjectType = {
        "dir1": {"class": "Directory", "location": "tests/wf/dir1/foo"},
        "dir2": {"class": "Directory", "location": "tests/wf/dir2/foo"},
    }

    def loadref(
        base: str, p: Union[CommentedMap, CommentedSeq, str, None]
    ) -> Union[CommentedMap, CommentedSeq, str, None]:
        if isinstance(p, dict):
            return p
        raise Exception("test case can't load things")

    scanned_deps = cast(
        List[Dict[str, Any]],
        cwltool.process.scandeps(
            "",
            obj,
            {"$import", "run"},
            {"$include", "$schemas", "location"},
            loadref,
            nestdirs=False,
        ),
    )

    scanned_deps.sort(key=lambda k: cast(str, k["basename"]))

    expected_deps = [
        {"basename": "foo", "class": "Directory", "location": "tests/wf/dir1/foo"},
        {"basename": "foo", "class": "Directory", "location": "tests/wf/dir2/foo"},
    ]

    assert scanned_deps == expected_deps


def test_scandeps_collision() -> None:
    stream = StringIO()

    assert (
        main(
            ["--print-deps", "--debug", get_data("tests/wf/dir_deps.json")],
            stdout=stream,
        )
        == 1
    )


def test_trick_scandeps() -> None:
    stream = StringIO()

    main(
        ["--print-deps", "--debug", get_data("tests/wf/trick_defaults.cwl")],
        stdout=stream,
    )
    assert json.loads(stream.getvalue())["secondaryFiles"][0]["location"][:2] != "_:"


def test_scandeps_defaults_with_secondaryfiles() -> None:
    stream = StringIO()

    main(
        [
            "--print-deps",
            "--relative-deps=cwd",
            "--debug",
            get_data("tests/wf/trick_defaults2.cwl"),
        ],
        stdout=stream,
    )
    assert json.loads(stream.getvalue())["secondaryFiles"][0]["secondaryFiles"][0][
        "location"
    ].endswith(os.path.join("tests", "wf", "indir1"))


def test_dedupe() -> None:
    not_deduped = [
        {"class": "File", "location": "file:///example/a"},
        {"class": "File", "location": "file:///example/a"},
        {"class": "File", "location": "file:///example/d"},
        {
            "class": "Directory",
            "location": "file:///example/c",
            "listing": [{"class": "File", "location": "file:///example/d"}],
        },
    ]  # type: List[CWLObjectType]

    expected = [
        {"class": "File", "location": "file:///example/a"},
        {
            "class": "Directory",
            "location": "file:///example/c",
            "listing": [{"class": "File", "location": "file:///example/d"}],
        },
    ]

    assert dedup(not_deduped) == expected


record = {
    "fields": [
        {
            "type": {"items": "string", "type": "array"},
            "name": "file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/description",
        },
        {
            "type": {"items": "File", "type": "array"},
            "name": "file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/vrn_file",
        },
    ],
    "type": "record",
    "name": "file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec",
}

source_to_sink = [
    (
        "0",
        {"items": ["string", "null"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        True,
    ),
    (
        "1",
        {"items": ["string"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        True,
    ),
    (
        "2",
        {"items": ["string", "null"], "type": "array"},
        {"items": ["string"], "type": "array"},
        True,
    ),
    (
        "3",
        {"items": ["string"], "type": "array"},
        {"items": ["int"], "type": "array"},
        False,
    ),
    ("record 0", record, record, True),
    ("record 1", record, {"items": "string", "type": "array"}, False),
]


@pytest.mark.parametrize("name, source, sink, expected", source_to_sink)
def test_compare_types(
    name: str, source: Dict[str, Any], sink: Dict[str, Any], expected: bool
) -> None:
    assert can_assign_src_to_sink(source, sink) == expected, name


source_to_sink_strict = [
    ("0", ["string", "null"], ["string", "null"], True),
    ("1", ["string"], ["string", "null"], True),
    ("2", ["string", "int"], ["string", "null"], False),
    (
        "3",
        {"items": ["string"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        True,
    ),
    (
        "4",
        {"items": ["string", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        False,
    ),
]


@pytest.mark.parametrize("name, source, sink, expected", source_to_sink_strict)
def test_compare_types_strict(
    name: str, source: Dict[str, Any], sink: Dict[str, Any], expected: bool
) -> None:
    assert can_assign_src_to_sink(source, sink, strict=True) == expected, name


typechecks = [
    (["string", "int"], ["string", "int", "null"], None, None, "pass"),
    (["string", "int"], ["string", "null"], None, None, "warning"),
    (["File", "int"], ["string", "null"], None, None, "exception"),
    (
        {"items": ["string", "int"], "type": "array"},
        {"items": ["string", "int", "null"], "type": "array"},
        None,
        None,
        "pass",
    ),
    (
        {"items": ["string", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        None,
        None,
        "warning",
    ),
    (
        {"items": ["File", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        None,
        None,
        "exception",
    ),
    # check linkMerge when sinktype is not an array
    (["string", "int"], ["string", "int", "null"], "merge_nested", None, "exception"),
    # check linkMerge: merge_nested
    (
        ["string", "int"],
        {"items": ["string", "int", "null"], "type": "array"},
        "merge_nested",
        None,
        "pass",
    ),
    (
        ["string", "int"],
        {"items": ["string", "null"], "type": "array"},
        "merge_nested",
        None,
        "warning",
    ),
    (
        ["File", "int"],
        {"items": ["string", "null"], "type": "array"},
        "merge_nested",
        None,
        "exception",
    ),
    # check linkMerge: merge_nested and sinktype is "Any"
    (["string", "int"], "Any", "merge_nested", None, "pass"),
    # check linkMerge: merge_flattened
    (
        ["string", "int"],
        {"items": ["string", "int", "null"], "type": "array"},
        "merge_flattened",
        None,
        "pass",
    ),
    (
        ["string", "int"],
        {"items": ["string", "null"], "type": "array"},
        "merge_flattened",
        None,
        "warning",
    ),
    (
        ["File", "int"],
        {"items": ["string", "null"], "type": "array"},
        "merge_flattened",
        None,
        "exception",
    ),
    (
        {"items": ["string", "int"], "type": "array"},
        {"items": ["string", "int", "null"], "type": "array"},
        "merge_flattened",
        None,
        "pass",
    ),
    (
        {"items": ["string", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        "merge_flattened",
        None,
        "warning",
    ),
    (
        {"items": ["File", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        "merge_flattened",
        None,
        "exception",
    ),
    # check linkMerge: merge_flattened and sinktype is "Any"
    (["string", "int"], "Any", "merge_flattened", None, "pass"),
    (
        {"items": ["string", "int"], "type": "array"},
        "Any",
        "merge_flattened",
        None,
        "pass",
    ),
    # check linkMerge: merge_flattened when srctype is a list
    (
        [{"items": "string", "type": "array"}],
        {"items": "string", "type": "array"},
        "merge_flattened",
        None,
        "pass",
    ),
    # check valueFrom
    (
        {"items": ["File", "int"], "type": "array"},
        {"items": ["string", "null"], "type": "array"},
        "merge_flattened",
        "special value",
        "pass",
    ),
]


@pytest.mark.parametrize(
    "src_type,sink_type,link_merge,value_from,expected_type", typechecks
)
def test_typechecking(
    src_type: Any, sink_type: Any, link_merge: str, value_from: Any, expected_type: str
) -> None:
    assert (
        cwltool.checker.check_types(
            src_type, sink_type, linkMerge=link_merge, valueFrom=value_from
        )
        == expected_type
    )


def test_lifting() -> None:
    # check that lifting the types of the process outputs to the workflow step
    # fails if the step 'out' doesn't match.
    factory = cwltool.factory.Factory()
    with pytest.raises(ValidationException):
        echo = factory.make(get_data("tests/test_bad_outputs_wf.cwl"))
        assert echo(inp="foo") == {"out": "foo\n"}


def test_malformed_outputs() -> None:
    # check that tool validation fails if one of the outputs is not a valid CWL type
    factory = cwltool.factory.Factory()
    with pytest.raises(ValidationException):
        factory.make(get_data("tests/wf/malformed_outputs.cwl"))()


def test_separate_without_prefix() -> None:
    # check that setting 'separate = false' on an inputBinding without prefix fails the workflow
    factory = cwltool.factory.Factory()
    with pytest.raises(WorkflowException):
        factory.make(get_data("tests/wf/separate_without_prefix.cwl"))()


def test_glob_expr_error(tmp_path: Path) -> None:
    """Better glob expression error."""
    error_code, _, stderr = get_main_output(
        [get_data("tests/wf/1496.cwl"), "--index", str(tmp_path)]
    )
    assert error_code != 0
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Resolved glob patterns must be strings" in stderr


def test_format_expr_error() -> None:
    """Better format expression error."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad_formattest.cwl"),
            get_data("tests/wf/formattest-job.json"),
        ]
    )
    assert error_code != 0
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "An expression in the 'format' field must evaluate to a string, or list "
        "of strings. However a non-string item was received: '42' of "
        "type '<class 'int'>'." in stderr
    )


def test_format_expr_error2() -> None:
    """Better format expression error, for a list of formats."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad_formattest2.cwl"),
            get_data("tests/wf/formattest-job.json"),
        ]
    )
    assert error_code != 0
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "bad_formattest2.cwl:14:9: For inputs, 'format' field can either contain "
        "a single CWL Expression or CWL Parameter Reference, a single format string, "
        "or a list of format strings. But the list cannot contain CWL Expressions "
        "or CWL Parameter References. List entry number 1 contains the following "
        "unallowed CWL Parameter Reference or Expression: '${ return "
        '["http://edamontology.org/format_2330", 42];}' in stderr
    )


def test_static_checker() -> None:
    # check that the static checker raises exception when a source type
    # mismatches its sink type.
    """Confirm that static type checker raises expected exception."""
    factory = cwltool.factory.Factory()

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf.cwl"))

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf2.cwl"))

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf3.cwl"))


@needs_docker
def test_circular_dependency_checker() -> None:
    # check that the circular dependency checker raises exception when there is
    # circular dependency in the workflow.
    """Confirm that circular dependency checker raises expected exception."""
    factory = cwltool.factory.Factory()

    with pytest.raises(
        ValidationException,
        match=r".*The\s*following\s*steps\s*have\s*circular\s*dependency:\s*.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf.cwl"))

    with pytest.raises(
        ValidationException,
        match=r".*#cat-a.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf.cwl"))

    with pytest.raises(
        ValidationException,
        match=r".*#ls.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf.cwl"))

    with pytest.raises(
        ValidationException,
        match=r".*#wc.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf.cwl"))

    with pytest.raises(
        ValidationException,
        match=r".*The\s*following\s*steps\s*have\s*circular\s*dependency:\s*.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf2.cwl"))

    with pytest.raises(
        ValidationException,
        match=r".*#ls.*",
    ):
        factory.make(get_data("tests/checker_wf/circ-dep-wf2.cwl"))


def test_var_spool_cwl_checker1() -> None:
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/non_portable.cwl"))
        assert (
            "non_portable.cwl:18:4: Non-portable reference to /var/spool/cwl detected"
            in stream.getvalue()
        )
    finally:
        _logger.removeHandler(streamhandler)


def test_var_spool_cwl_checker2() -> None:
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/non_portable2.cwl"))
        assert (
            "non_portable2.cwl:19:4: Non-portable reference to /var/spool/cwl detected"
            in stream.getvalue()
        )
    finally:
        _logger.removeHandler(streamhandler)


def test_var_spool_cwl_checker3() -> None:
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/portable.cwl"))
        assert (
            "Non-portable reference to /var/spool/cwl detected" not in stream.getvalue()
        )
    finally:
        _logger.removeHandler(streamhandler)


def test_print_dot() -> None:
    # print Workflow
    cwl_path = get_data("tests/wf/three_step_color.cwl")
    expected_dot = pydot.graph_from_dot_data(
        """
    digraph {{
        graph [bgcolor="#eeeeee",
                clusterrank=local,
                labeljust=right,
                labelloc=bottom
        ];
        subgraph cluster_inputs {{
                graph [label="Workflow Inputs",
                        rank=same,
                        style=dashed
                ];
                "file_input"        [fillcolor="#94DDF4",
                        label=file_input,
                        style=filled];
        }}
        subgraph cluster_outputs {{
                graph [label="Workflow Outputs",
                        labelloc=b,
                        rank=same,
                        style=dashed
                ];
                "file_output"       [fillcolor="#94DDF4",
                        label=file_output,
                        style=filled];
                "string_output"       [fillcolor="#94DDF4",
                        label=string_output,
                        style=filled];
        }}
        "nested_workflow" [fillcolor="#F3CEA1",
                label=nested_workflow,
                style=filled];
        "operation"      [fillcolor=lightgoldenrodyellow,
                label=operation,
                style=dashed];
        "command_line_tool"      [fillcolor=lightgoldenrodyellow,
                label=command_line_tool,
                style=filled];
        "file_input" -> "nested_workflow";
        "nested_workflow" -> "operation";
        "operation" -> "command_line_tool";
        "operation" -> "string_output";
        "command_line_tool" -> "file_output";
}}
    """.format()
    )[0]
    stdout = StringIO()
    assert main(["--debug", "--print-dot", cwl_path], stdout=stdout) == 0
    computed_dot = pydot.graph_from_dot_data(stdout.getvalue())[0]
    computed_edges = sorted(
        (source, target) for source, target in computed_dot.obj_dict["edges"]
    )
    expected_edges = sorted(
        (source, target) for source, target in expected_dot.obj_dict["edges"]
    )
    assert computed_edges == expected_edges

    # print CommandLineTool
    cwl_path = get_data("tests/wf/echo.cwl")
    stdout = StringIO()
    assert main(["--debug", "--print-dot", cwl_path], stdout=stdout) == 1


test_factors = [(""), ("--parallel"), ("--debug"), ("--parallel --debug")]


@pytest.mark.parametrize("factor", test_factors)
def test_js_console_cmd_line_tool(
    factor: str, caplog: pytest.LogCaptureFixture
) -> None:
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(
            ["--js-console", "--no-container", get_data("tests/wf/" + test_file)]
        )
        error_code, _, _ = get_main_output(commands)
        logging_output = "\n".join([record.message for record in caplog.records])
        assert "[log] Log message" in logging_output
        assert "[err] Error message" in logging_output

        assert error_code == 0, logging_output


@pytest.mark.parametrize("factor", test_factors)
def test_no_js_console(factor: str) -> None:
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(["--no-container", get_data("tests/wf/" + test_file)])
        _, _, stderr = get_main_output(commands)

        stderr = re.sub(r"\s\s+", " ", stderr)
        assert "[log] Log message" not in stderr
        assert "[err] Error message" not in stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_dir(tmp_path: Path, factor: str) -> None:
    """Test --cidfile-dir option works."""
    test_file = "cache_test_workflow.cwl"
    with working_directory(tmp_path):
        commands = factor.split()
        commands.extend(
            ["--cidfile-dir", str(tmp_path), get_data("tests/wf/" + test_file)]
        )
        error_code, stdout, stderr = get_main_output(commands)
        stderr = re.sub(r"\s\s+", " ", stderr)
        assert "completed success" in stderr
        assert error_code == 0
        cidfiles = list(tmp_path.glob("**/*.cid"))
        cidfiles_count = len(cidfiles)
        assert cidfiles_count == 2, f"Should be 2 cidfiles, but got {cidfiles}"


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_dir_arg_is_file_instead_of_dir(tmp_path: Path, factor: str) -> None:
    """Test --cidfile-dir with a file produces the correct error."""
    test_file = "cache_test_workflow.cwl"
    bad_cidfile_dir = tmp_path / "cidfile-dir-actually-a-file"
    bad_cidfile_dir.touch()
    commands = factor.split()
    commands.extend(
        ["--cidfile-dir", str(bad_cidfile_dir), get_data("tests/wf/" + test_file)]
    )
    error_code, _, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "is not a directory, please check it first" in stderr, stderr
    assert error_code == 2 or error_code == 1, stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_non_existing_dir(tmp_path: Path, factor: str) -> None:
    """Test that --cachedir with a bad path should produce a specific error."""
    test_file = "cache_test_workflow.cwl"
    bad_cidfile_dir = tmp_path / "cidfile-dir-badpath"
    commands = factor.split()
    commands.extend(
        [
            "--record-container-id",
            "--cidfile-dir",
            str(bad_cidfile_dir),
            get_data("tests/wf/" + test_file),
        ]
    )
    error_code, _, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "directory doesn't exist, please create it first" in stderr, stderr
    assert error_code == 2 or error_code == 1, stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_w_prefix(tmp_path: Path, factor: str) -> None:
    """Test that --cidfile-prefix works."""
    test_file = "cache_test_workflow.cwl"
    with working_directory(tmp_path):
        try:
            commands = factor.split()
            commands.extend(
                [
                    "--record-container-id",
                    "--cidfile-prefix=pytestcid",
                    get_data("tests/wf/" + test_file),
                ]
            )
            error_code, stdout, stderr = get_main_output(commands)
        finally:
            listing = tmp_path.iterdir()
            cidfiles_count = sum(1 for _ in tmp_path.glob("**/pytestcid*"))
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0
    assert cidfiles_count == 2, f"{list(listing)}/n{stderr}"


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_v1_1(factor: str, tmp_path: Path) -> None:
    test_file = "secondary-files.cwl"
    test_job_file = "secondary-files-job.yml"
    try:
        old_umask = os.umask(stat.S_IWOTH)  # test run with umask 002
        commands = factor.split()
        commands.extend(
            [
                "--debug",
                "--outdir",
                str(tmp_path),
                get_data(os.path.join("tests", test_file)),
                get_data(os.path.join("tests", test_job_file)),
            ]
        )
        error_code, _, stderr = get_main_output(commands)
    finally:
        # 664 in octal, '-rw-rw-r--'
        assert stat.S_IMODE(os.stat(tmp_path / "lsout").st_mode) == 436
        os.umask(old_umask)  # revert back to original umask
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_bad_v1_1(factor: str, tmp_path: Path) -> None:
    """Affirm the correct error message for a bad secondaryFiles expression."""
    test_file = "secondary-files-bad.cwl"
    test_job_file = "secondary-files-job.yml"
    commands = factor.split()
    commands.extend(
        [
            "--outdir",
            str(tmp_path),
            get_data(os.path.join("tests", test_file)),
            get_data(os.path.join("tests", test_job_file)),
        ]
    )
    error_code, _, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "The result of a expression in the field 'required' must be a bool "
        "or None, not a <class 'int'>." in stderr
    ), stderr
    assert error_code == 1


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_v1_0(tmp_path: Path, factor: str) -> None:
    """Test plain strings under "secondaryFiles"."""
    test_file = "secondary-files-string-v1.cwl"
    test_job_file = "secondary-files-job.yml"
    commands = factor.split()
    commands.extend(
        [
            "--outdir",
            str(tmp_path),
            get_data(os.path.join("tests", test_file)),
            get_data(os.path.join("tests", test_job_file)),
        ]
    )
    error_code, _, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_wf_without_container(tmp_path: Path, factor: str) -> None:
    """Confirm that we can run a workflow without a container."""
    test_file = "hello-workflow.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(
        [
            "--cachedir",
            cache_dir,
            "--outdir",
            str(tmp_path / "outdir"),
            get_data("tests/wf/" + test_file),
            "--usermessage",
            "hello",
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_issue_740_fixed(tmp_path: Path, factor: str) -> None:
    """Confirm that re-running a particular workflow with caching succeeds."""
    test_file = "cache_test_workflow.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0

    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Output of job will be cached in" not in stderr
    assert error_code == 0, stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cache_relative_paths(tmp_path: Path, factor: str) -> None:
    """Confirm that re-running a particular workflow with caching succeeds."""
    test_file = "secondary-files.cwl"
    test_job_file = "secondary-files-job.yml"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(
        [
            "--cachedir",
            cache_dir,
            get_data(f"tests/{test_file}"),
            get_data(f"tests/{test_job_file}"),
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0

    commands = factor.split()
    commands.extend(
        [
            "--cachedir",
            cache_dir,
            get_data(f"tests/{test_file}"),
            get_data(f"tests/{test_job_file}"),
        ]
    )
    error_code, _, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "Output of job will be cached in" not in stderr
    assert error_code == 0, stderr

    assert (tmp_path / "cwltool_cache" / "27903451fc1ee10c148a0bdeb845b2cf").exists()


@needs_docker
def test_compute_checksum() -> None:
    runtime_context = RuntimeContext()
    runtime_context.compute_checksum = True
    runtime_context.use_container = False
    factory = cwltool.factory.Factory(runtime_context=runtime_context)
    echo = factory.make(get_data("tests/wf/cat-tool.cwl"))
    output = echo(
        file1={"class": "File", "location": get_data("tests/wf/whale.txt")},
        reverse=False,
    )
    assert isinstance(output, dict)
    result = output["output"]
    assert isinstance(result, dict)
    assert result["checksum"] == "sha1$327fc7aedf4f6b69a42a7c8b808dc5a7aff61376"


def test_bad_stdin_expr_error() -> None:
    """Confirm that a bad stdin expression gives a useful error."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad-stdin-expr.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ]
    )
    assert error_code == 1
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "'stdin' expression must return a string or null. Got '1111' for '$(inputs.file1.size)'."
        in stderr
    )


def test_bad_stderr_expr_error() -> None:
    """Confirm that a bad stderr expression gives a useful error."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad-stderr-expr.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ]
    )
    assert error_code == 1
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "'stderr' expression must return a string. Got '1111' for '$(inputs.file1.size)'."
        in stderr
    )


def test_bad_stdout_expr_error() -> None:
    """Confirm that a bad stdout expression gives a useful error."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad-stdout-expr.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ]
    )
    assert error_code == 1
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "'stdout' expression must return a string. Got '1111' for '$(inputs.file1.size)'."
        in stderr
    )


@needs_docker
def test_stdin_with_id_preset() -> None:
    """Confirm that a type: stdin with a preset id does not give an error."""
    error_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/1590.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ]
    )
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_no_compute_chcksum(tmp_path: Path, factor: str) -> None:
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    commands = factor.split()
    commands.extend(
        [
            "--no-compute-checksum",
            "--outdir",
            str(tmp_path),
            get_data(test_file),
            get_data(job_file),
        ]
    )
    error_code, stdout, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0
    assert "checksum" not in stdout


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_bad_userspace_runtime(factor: str) -> None:
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    commands = factor.split()
    commands.extend(
        [
            "--user-space-docker-cmd=quaquioN",
            "--default-container=docker.io/debian:stable-slim",
            get_data(test_file),
            get_data(job_file),
        ]
    )
    error_code, stdout, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "or quaquioN is missing or broken" in stderr, stderr
    assert error_code == 1


@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand(factor: str) -> None:
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "'neenooGo' not found" in stderr, stderr
    assert error_code == 1


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand_docker(factor: str) -> None:
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend(
        [
            "--debug",
            "--default-container",
            "docker.io/debian:stable-slim",
            get_data(test_file),
        ]
    )
    error_code, stdout, stderr = get_main_output(commands)
    assert "permanentFail" in stderr, stderr
    assert error_code == 1


@pytest.mark.parametrize("factor", test_factors)
def test_v1_0_position_expression(factor: str) -> None:
    test_file = "tests/echo-position-expr.cwl"
    test_job = "tests/echo-position-expr-job.yml"
    commands = factor.split()
    commands.extend(["--debug", get_data(test_file), get_data(test_job)])
    error_code, stdout, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "is not int" in stderr, stderr
    assert error_code == 1


@pytest.mark.parametrize("factor", test_factors)
def test_v1_1_position_badexpression(factor: str) -> None:
    """Test for the correct error for a bad position expression."""
    test_file = "tests/echo-badposition-expr.cwl"
    test_job = "tests/echo-position-expr-job.yml"
    commands = factor.split()
    commands.extend(["--debug", get_data(test_file), get_data(test_job)])
    error_code, _, stderr = get_main_output(commands)
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "expressions must evaluate to an int" in stderr, stderr
    assert error_code == 1


@pytest.mark.parametrize("factor", test_factors)
def test_optional_numeric_output_0(factor: str) -> None:
    test_file = "tests/wf/optional-numerical-output-0.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0
    assert json.loads(stdout)["out"] == 0


@pytest.mark.parametrize("factor", test_factors)
def test_env_filtering(factor: str) -> None:
    test_file = "tests/env.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)

    process = subprocess.Popen(
        [
            "sh",
            "-c",
            r"""getTrueShellExeName() {
  local trueExe nextTarget 2>/dev/null
  trueExe=$(ps -o comm= $$) || return 1
  [ "${trueExe#-}" = "$trueExe" ] || trueExe=${trueExe#-}
  [ "${trueExe#/}" != "$trueExe" ] || trueExe=$([ -n "$ZSH_VERSION" ] && which -p "$trueExe" || which "$trueExe")
  while nextTarget=$(readlink "$trueExe"); do trueExe=$nextTarget; done
  printf '%s\n' "$(basename "$trueExe")"
} ; getTrueShellExeName""",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=None,
    )
    sh_name_b, sh_name_err = process.communicate()
    assert sh_name_b
    sh_name = sh_name_b.decode("utf-8").strip()

    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr, (error_code, stdout, stderr)
    assert error_code == 0, (error_code, stdout, stderr)
    if sh_name == "dash":
        target = 4
    else:  # bash adds "SHLVL" and "_" environment variables
        target = 6
    result = json.loads(stdout)["env_count"]
    details = ""
    if result != target:
        _, details, _ = get_main_output(["--quiet", get_data("tests/env2.cwl")])
        print(sh_name)
        print(sh_name_err)
        print(details)
    assert result == target, (error_code, sh_name, sh_name_err, details, stdout, stderr)


def test_v1_0_arg_empty_prefix_separate_false() -> None:
    test_file = "tests/arg-empty-prefix-separate-false.cwl"
    error_code, stdout, stderr = get_main_output(
        ["--debug", get_data(test_file), "--echo"]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "completed success" in stderr
    assert error_code == 0


def test_scatter_output_filenames(tmp_path: Path) -> None:
    """If a scatter step produces identically named output then confirm that the final output is renamed correctly."""
    cwd = Path.cwd()
    with working_directory(tmp_path):
        rtc = RuntimeContext()
        rtc.outdir = str(cwd)
        factory = cwltool.factory.Factory(runtime_context=rtc)
        output_names = ["output.txt", "output.txt_2", "output.txt_3"]
        scatter_workflow = factory.make(get_data("tests/scatter_numbers.cwl"))
        result = scatter_workflow(range=3)
        assert isinstance(result, dict)
        assert "output" in result

        locations = sorted(element["location"] for element in result["output"])

        assert (
            locations[0].endswith("output.txt")
            and locations[1].endswith("output.txt_2")
            and locations[2].endswith("output.txt_3")
        ), f"Locations {locations} do not end with {output_names}"


def test_malformed_hints() -> None:
    """Confirm that empty hints section is caught."""
    factory = cwltool.factory.Factory()
    with pytest.raises(
        ValidationException,
        match=r".*wc-tool-bad-hints\.cwl:6:1:\s*If\s*'hints'\s*is\s*present\s*then\s*it\s*must\s*be\s*a\s*list.*",
    ):
        factory.make(get_data("tests/wc-tool-bad-hints.cwl"))


def test_malformed_reqs() -> None:
    """Confirm that empty reqs section is caught."""
    factory = cwltool.factory.Factory()
    with pytest.raises(
        ValidationException,
        match=r".*wc-tool-bad-reqs\.cwl:6:1:\s*If\s*'requirements'\s*is\s*present\s*then\s*it\s*must\s*be\s*a\s*list.*",
    ):
        factory.make(get_data("tests/wc-tool-bad-reqs.cwl"))


def test_arguments_self() -> None:
    """Confirm that $(self) works in the arguments list."""
    factory = cwltool.factory.Factory()
    if not shutil.which("docker"):
        if shutil.which("podman"):
            factory.runtime_context.podman = True
            factory.loading_context.podman = True
        elif shutil.which("singularity"):
            factory.runtime_context.singularity = True
            factory.loading_context.singularity = True
        elif not shutil.which("jq"):
            pytest.skip(
                "Need a container engine (docker, podman, or singularity) or jq to run this test."
            )
        else:
            factory.runtime_context.use_container = False
    check = factory.make(get_data("tests/wf/paramref_arguments_self.cwl"))
    outputs = cast(Dict[str, Any], check())
    assert "self_review" in outputs
    assert len(outputs) == 1
    assert (
        outputs["self_review"]["checksum"]
        == "sha1$724ba28f4a9a1b472057ff99511ed393a45552e1"
    )


def test_bad_timelimit_expr() -> None:
    """Confirm error message for bad timelimit expression."""
    err_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad_timelimit.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "'timelimit' expression must evaluate to a long/int. "
        "Got '42' for expression '${return \"42\";}" in stderr
    )
    assert err_code == 1


def test_bad_networkaccess_expr() -> None:
    """Confirm error message for bad networkaccess expression."""
    err_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/bad_networkaccess.cwl"),
        ]
    )
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert (
        "'networkAccess' expression must evaluate to a bool. "
        "Got '42' for expression '${return 42;}" in stderr
    )
    assert err_code == 1


def test_staging_files_in_any() -> None:
    """Confirm that inputs of type File are staged, even if the schema is Any."""
    err_code, _, stderr = get_main_output(
        [get_data("tests/wf/816_wf.cwl"), "--file", get_data("tests/echo-job.yaml")]
    )
    assert err_code == 0


def test_custom_type_in_step_process() -> None:
    """Test that any needed custom types are available when processing a WorkflowStep."""
    err_code, _, stderr = get_main_output(
        [
            get_data("tests/wf/811.cwl"),
            get_data("tests/wf/811_inputs.yml"),
        ]
    )
    assert err_code == 0


def test_expression_tool_class() -> None:
    """Confirm properties of the ExpressionTool class."""
    factory = cwltool.factory.Factory()
    tool_path = get_data("tests/wf/parseInt-tool.cwl")
    expression_tool = factory.make(tool_path).t
    assert str(expression_tool) == f"ExpressionTool: file://{tool_path}"


def test_operation_class() -> None:
    """Confirm properties of the AbstractOperation class."""
    factory = cwltool.factory.Factory()
    tool_path = get_data("tests/wf/operation/abstract-cosifer.cwl")
    expression_tool = factory.make(tool_path).t
    assert str(expression_tool) == f"AbstractOperation: file://{tool_path}"


def test_command_line_tool_class() -> None:
    """Confirm properties of the CommandLineTool class."""
    factory = cwltool.factory.Factory()
    tool_path = get_data("tests/echo.cwl")
    expression_tool = factory.make(tool_path).t
    assert str(expression_tool) == f"CommandLineTool: file://{tool_path}"


def test_record_default_with_long() -> None:
    """Confirm that record defaults are respected."""
    tool_path = get_data("tests/wf/paramref_arguments_roundtrip.cwl")
    err_code, stdout, stderr = get_main_output([tool_path])
    assert err_code == 0
    result = json.loads(stdout)["same_record"]
    assert result["first"] == "y"
    assert result["second"] == 23
    assert result["third"] == 2.3
    assert result["fourth"] == 4242424242
    assert result["fifth"] == 4200000000000000000000000000000000000000000
    assert result["sixth"]["class"] == "File"
    assert result["sixth"]["basename"] == "whale.txt"
    assert result["sixth"]["size"] == 1111
    assert (
        result["sixth"]["checksum"] == "sha1$327fc7aedf4f6b69a42a7c8b808dc5a7aff61376"
    )


def test_record_outputeval(tmp_path: Path) -> None:
    """Confirm that record types can be populated from outputEval."""
    tool_path = get_data("tests/wf/record_outputeval.cwl")
    err_code, stdout, stderr = get_main_output(["--outdir", str(tmp_path), tool_path])
    assert err_code == 0
    result = json.loads(stdout)["references"]
    assert "genome_fa" in result
    assert result["genome_fa"]["class"] == "File"
    assert result["genome_fa"]["basename"] == "GRCm38.primary_assembly.genome.fa"
    assert (
        result["genome_fa"]["checksum"]
        == "sha1$da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )
    assert result["genome_fa"]["size"] == 0
    assert "annotation_gtf" in result
    assert result["annotation_gtf"]["class"] == "File"
    assert (
        result["annotation_gtf"]["basename"]
        == "gencode.vM21.primary_assembly.annotation.gtf"
    )
    assert (
        result["annotation_gtf"]["checksum"]
        == "sha1$da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )
    assert result["annotation_gtf"]["size"] == 0


def tests_outputsource_valid_identifier_invalid_source() -> None:
    """Confirm error for invalid source that was also a valid identifier."""
    tool_path = get_data("tests/checker_wf/broken-wf4.cwl")
    err_code, stdout, stderr = get_main_output([tool_path])
    assert err_code == 1
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert "tests/checker_wf/broken-wf4.cwl:12:5: outputSource not found" in stderr
    assert "tests/checker_wf/broken-wf4.cwl#echo_w" in stderr


def test_mismatched_optional_arrays() -> None:
    """Ignore 'null' when comparing array types."""
    factory = cwltool.factory.Factory()

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/optional_array_mismatch.cwl"))


def test_validate_optional_src_with_mandatory_sink() -> None:
    """Confirm expected warning with an optional File connected to a mandatory File."""
    exit_code, stdout, stderr = get_main_output(
        ["--validate", get_data("tests/wf/optional_src_mandatory_sink.cwl")]
    )
    assert exit_code == 0
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert 'Source \'opt_file\' of type ["null", "File"] may be incompatible' in stderr
    assert "with sink 'r' of type \"File\"" in stderr
