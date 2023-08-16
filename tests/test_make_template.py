"""Tests for --make-template."""

from schema_salad.sourceline import cmap

from cwltool import main


def test_anonymous_record() -> None:
    inputs = cmap([{"type": "record", "fields": []}])
    assert main.generate_example_input(inputs, None) == ({}, "Anonymous record type.")


def test_union() -> None:
    """Test for --make-template for a union type."""
    inputs = cmap(["string", "string[]"])
    assert main.generate_example_input(inputs, None) == (
        "a_string",
        "one of type 'string', type 'string[]'",
    )


def test_optional_union() -> None:
    """Test for --make-template for an optional union type."""
    inputs = cmap(["null", "string", "string[]"])
    assert main.generate_example_input(inputs, None) == (
        "a_string",
        "one of type 'string', type 'string[]' (optional)",
    )
