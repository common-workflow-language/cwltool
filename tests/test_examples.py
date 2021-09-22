import json
import logging
import os
import re
import stat
import subprocess
import sys
import shutil
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Union, cast
from urllib.parse import urlparse

import pydot  # type: ignore
import pytest
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.exceptions import ValidationException

import cwltool.checker
import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from cwltool.checker import can_assign_src_to_sink
from cwltool.context import RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.main import main
from cwltool.process import CWL_IANA
from cwltool.sandboxjs import JavascriptException
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
    match = expr.param_re.match(expression)
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


def test_input_deps() -> None:
    stream = StringIO()

    main(
        [
            "--print-input-deps",
            get_data("tests/wf/count-lines1-wf.cwl"),
            get_data("tests/wf/wc-job.json"),
        ],
        stdout=stream,
    )

    expected = {
        "class": "File",
        "location": "wc-job.json",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": "whale.txt",
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts() -> None:
    stream = StringIO()

    main(
        [
            "--print-input-deps",
            get_data("tests/wf/count-lines1-wf.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ],
        stdout=stream,
    )
    expected = {
        "class": "File",
        "location": "",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": "whale.txt",
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts_relative_deps_cwd() -> None:
    stream = StringIO()

    data_path = get_data("tests/wf/whale.txt")
    main(
        [
            "--print-input-deps",
            "--relative-deps",
            "cwd",
            get_data("tests/wf/count-lines1-wf.cwl"),
            "--file1",
            data_path,
        ],
        stdout=stream,
    )

    goal = {
        "class": "File",
        "location": "",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": str(Path(os.path.relpath(data_path, os.path.curdir))),
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == goal


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


def test_static_checker() -> None:
    # check that the static checker raises exception when a source type
    # mismatches its sink type.
    factory = cwltool.factory.Factory()

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf.cwl"))

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf2.cwl"))

    with pytest.raises(ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf3.cwl"))


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
    cwl_path = get_data("tests/wf/revsort.cwl")
    cwl_posix_path = Path(cwl_path).as_posix()
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
                "file://{cwl_posix_path}#workflow_input"      [fillcolor="#94DDF4",
                        label=workflow_input,
                        style=filled];
                "file://{cwl_posix_path}#reverse_sort"        [fillcolor="#94DDF4",
                        label=reverse_sort,
                        style=filled];
        }}
        subgraph cluster_outputs {{
                graph [label="Workflow Outputs",
                        labelloc=b,
                        rank=same,
                        style=dashed
                ];
                "file://{cwl_posix_path}#sorted_output"       [fillcolor="#94DDF4",
                        label=sorted_output,
                        style=filled];
        }}
        "file://{cwl_posix_path}#rev" [fillcolor=lightgoldenrodyellow,
                label=rev,
                style=filled];
        "file://{cwl_posix_path}#sorted"      [fillcolor=lightgoldenrodyellow,
                label=sorted,
                style=filled];
        "file://{cwl_posix_path}#rev" -> "file://{cwl_posix_path}#sorted";
        "file://{cwl_posix_path}#sorted" -> "file://{cwl_posix_path}#sorted_output";
        "file://{cwl_posix_path}#workflow_input" -> "file://{cwl_posix_path}#rev";
        "file://{cwl_posix_path}#reverse_sort" -> "file://{cwl_posix_path}#sorted";
}}
    """.format(
            cwl_posix_path=cwl_posix_path
        )
    )[0]
    stdout = StringIO()
    assert main(["--print-dot", cwl_path], stdout=stdout) == 0
    computed_dot = pydot.graph_from_dot_data(stdout.getvalue())[0]
    computed_edges = sorted(
        (urlparse(source).fragment, urlparse(target).fragment)
        for source, target in computed_dot.obj_dict["edges"]
    )
    expected_edges = sorted(
        (urlparse(source).fragment, urlparse(target).fragment)
        for source, target in expected_dot.obj_dict["edges"]
    )
    assert computed_edges == expected_edges

    # print CommandLineTool
    cwl_path = get_data("tests/wf/echo.cwl")
    stdout = StringIO()
    assert main(["--debug", "--print-dot", cwl_path], stdout=stdout) == 1


test_factors = [(""), ("--parallel"), ("--debug"), ("--parallel --debug")]


@pytest.mark.parametrize("factor", test_factors)
def test_js_console_cmd_line_tool(factor: str) -> None:
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(
            ["--js-console", "--no-container", get_data("tests/wf/" + test_file)]
        )
        error_code, _, stderr = get_main_output(commands)

        assert "[log] Log message" in stderr
        assert "[err] Error message" in stderr

        assert error_code == 0, stderr


@pytest.mark.parametrize("factor", test_factors)
def test_no_js_console(factor: str) -> None:
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(["--no-container", get_data("tests/wf/" + test_file)])
        _, _, stderr = get_main_output(commands)

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
        assert "completed success" in stderr
        assert error_code == 0
        cidfiles_count = sum(1 for _ in tmp_path.glob("**/*"))
        assert cidfiles_count == 2


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
    assert "completed success" in stderr
    assert error_code == 0
    assert cidfiles_count == 2, f"{list(listing)}/n{stderr}"


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_v1_1(factor: str) -> None:
    test_file = "secondary-files.cwl"
    test_job_file = "secondary-files-job.yml"
    try:
        old_umask = os.umask(stat.S_IWOTH)  # test run with umask 002
        commands = factor.split()
        commands.extend(
            [
                "--debug",
                get_data(os.path.join("tests", test_file)),
                get_data(os.path.join("tests", test_job_file)),
            ]
        )
        error_code, _, stderr = get_main_output(commands)
    finally:
        # 664 in octal, '-rw-rw-r--'
        assert stat.S_IMODE(os.stat("lsout").st_mode) == 436
        os.umask(old_umask)  # revert back to original umask
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_bad_v1_1(factor: str) -> None:
    """Affirm the correct error message for a bad secondaryFiles expression."""
    test_file = "secondary-files-bad.cwl"
    test_job_file = "secondary-files-job.yml"
    commands = factor.split()
    commands.extend(
        [
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

    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_issue_740_fixed(tmp_path: Path, factor: str) -> None:
    """Confirm that re-running a particular workflow with caching suceeds."""
    test_file = "cache_test_workflow.cwl"
    cache_dir = str(tmp_path / "cwltool_cache")
    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    assert "completed success" in stderr
    assert error_code == 0

    commands = factor.split()
    commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)

    assert "Output of job will be cached in" not in stderr
    assert error_code == 0, stderr


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
    assert "completed success" in stderr
    assert error_code == 0
    assert "checksum" not in stdout


@pytest.mark.parametrize("factor", test_factors)
def test_bad_userspace_runtime(factor: str) -> None:
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    commands = factor.split()
    commands.extend(
        [
            "--user-space-docker-cmd=quaquioN",
            "--default-container=debian",
            get_data(test_file),
            get_data(job_file),
        ]
    )
    error_code, stdout, stderr = get_main_output(commands)
    assert "or quaquioN is missing or broken" in stderr, stderr
    assert error_code == 1


@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand(factor: str) -> None:
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "'neenooGo' not found" in stderr, stderr
    assert error_code == 1


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand_docker(factor: str) -> None:
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend(["--debug", "--default-container", "debian", get_data(test_file)])
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
        match=r".*wc-tool-bad-hints\.cwl:6:1: If 'hints' is\s*present\s*then\s*it\s*must\s*be\s*a\s*list.*",
    ):
        factory.make(get_data("tests/wc-tool-bad-hints.cwl"))


def test_malformed_reqs() -> None:
    """Confirm that empty reqs section is caught."""
    factory = cwltool.factory.Factory()
    with pytest.raises(
        ValidationException,
        match=r".*wc-tool-bad-reqs\.cwl:6:1: If 'requirements' is\s*present\s*then\s*it\s*must\s*be\s*a\s*list.*",
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
                "Need a container engine (docker, podman, or signularity) or jq to run this test."
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
