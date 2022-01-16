"""Tests for --make-template."""

from schema_salad.sourceline import cmap

from cwltool import main


def test_anonymous_record() -> None:
    inputs = cmap([{"type": "record", "fields": []}])
    assert main.generate_example_input(inputs, None) == ({}, "Anonymous record type.")
