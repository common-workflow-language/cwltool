"""Tests for --make-template."""
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
from urllib.parse import urlparse

from schema_salad.sourceline import cmap
from cwltool import main
from .util import get_data, get_main_output, needs_docker, working_directory


def test_anonymous_record() -> None:
    inputs = cmap([{"type": "record", "fields": []}])
    assert main.generate_example_input(inputs, None) == ({}, "Anonymous record type.")
