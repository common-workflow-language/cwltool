from __future__ import absolute_import
import unittest

from cwltool.pathmapper import PathMapper, normalizeFilesDirs


class TestPathMapper(unittest.TestCase):
    def test_subclass(self):
        class SubPathMapper(PathMapper):
            def __init__(self, referenced_files, basedir, stagedir, new):
                super(SubPathMapper, self).__init__(referenced_files, basedir, stagedir)
                self.new = new

        a = SubPathMapper([], '', '', "new")
        self.assertTrue(a.new, "new")

    def test_strip_trailing(self):
        d = {
                "class": "Directory",
                "location": "/foo/bar/"
            }
        normalizeFilesDirs(d)
        self.assertEqual(
            {
                "class": "Directory",
                "location": "/foo/bar",
                "basename": "bar"
            },
            d)

    def test_basename_field_generation(self):
        base_file = {
            "class": "File",
            "location": "/foo/"
        }
        # (filename, expected: (nameroot, nameext))
        testdata = [
            ("foo.bar",     ("foo",     ".bar")),
            ("foo",         ("foo",     '')),
            (".foo",        (".foo",    '')),
            ("foo.",        ("foo",    '.')),
            ("foo.bar.baz", ("foo.bar", ".baz"))
        ]

        for filename, (nameroot, nameext) in testdata:
            file = dict(base_file)
            file["location"] = file["location"] + filename

            expected = dict(file)
            expected["basename"] = filename
            expected["nameroot"] = nameroot
            expected["nameext"] = nameext

            normalizeFilesDirs(file)
            self.assertEqual(file, expected)

    def test_normalizeFilesDirs(self):
        n = {
            "class": "File",
            "location": "file1.txt"
        }
        normalizeFilesDirs(n)
        self.assertEqual(n, {
            "class": "File",
            "location": "file1.txt",
            'basename': 'file1.txt',
            'nameext': '.txt',
            'nameroot': 'file1'
        })

        n = {
            "class": "File",
            "location": "file:///foo/file1.txt"
        }
        normalizeFilesDirs(n)
        self.assertEqual(n, {
            "class": "File",
            "location": "file:///foo/file1.txt",
            'basename': 'file1.txt',
            'nameext': '.txt',
            'nameroot': 'file1'
        })

        n = {
            "class": "File",
            "location": "http://example.com/file1.txt"
        }
        normalizeFilesDirs(n)
        self.assertEqual(n, {
            "class": "File",
            "location": "http://example.com/file1.txt",
            'basename': 'file1.txt',
            'nameext': '.txt',
            'nameroot': 'file1'
        })
