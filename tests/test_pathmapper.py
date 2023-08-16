from typing import List, Tuple

import pytest

from cwltool.pathmapper import PathMapper
from cwltool.utils import CWLObjectType, normalizeFilesDirs


def test_subclass() -> None:
    class SubPathMapper(PathMapper):
        def __init__(
            self,
            referenced_files: List[CWLObjectType],
            basedir: str,
            stagedir: str,
            new: str,
        ):
            super().__init__(referenced_files, basedir, stagedir)
            self.new = new

    pathmap = SubPathMapper([], "", "", "new")
    assert pathmap.new is not None, "new"


normalization_parameters = [
    (
        "strip trailing slashes",
        {"class": "Directory", "location": "/foo/bar/"},
        {"class": "Directory", "location": "/foo/bar", "basename": "bar"},
    ),
    (
        "file",
        {"class": "File", "location": "file1.txt"},
        {
            "class": "File",
            "location": "file1.txt",
            "basename": "file1.txt",
            "nameext": ".txt",
            "nameroot": "file1",
        },
    ),
    (
        "file with local uri",
        {"class": "File", "location": "file:///foo/file1.txt"},
        {
            "class": "File",
            "location": "file:///foo/file1.txt",
            "basename": "file1.txt",
            "nameext": ".txt",
            "nameroot": "file1",
        },
    ),
    (
        "file with http url",
        {"class": "File", "location": "http://example.com/file1.txt"},
        {
            "class": "File",
            "location": "http://example.com/file1.txt",
            "basename": "file1.txt",
            "nameext": ".txt",
            "nameroot": "file1",
        },
    ),
]


@pytest.mark.parametrize("name,file_dir,expected", normalization_parameters)
def test_normalizeFilesDirs(name: str, file_dir: CWLObjectType, expected: CWLObjectType) -> None:
    normalizeFilesDirs(file_dir)
    assert file_dir == expected, name


# (filename, expected: (nameroot, nameext))
basename_generation_parameters = [
    ("foo.bar", ("foo", ".bar")),
    ("foo", ("foo", "")),
    (".foo", (".foo", "")),
    ("foo.", ("foo", ".")),
    ("foo.bar.baz", ("foo.bar", ".baz")),
]


@pytest.mark.parametrize("filename,expected", basename_generation_parameters)
def test_basename_field_generation(filename: str, expected: Tuple[str, str]) -> None:
    nameroot, nameext = expected
    expected2 = {
        "class": "File",
        "location": "/foo/" + filename,
        "basename": filename,
        "nameroot": nameroot,
        "nameext": nameext,
    }

    my_file = {"class": "File", "location": "/foo/" + filename}

    normalizeFilesDirs(my_file)
    assert my_file == expected2
