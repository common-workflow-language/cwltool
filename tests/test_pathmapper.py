import pytest

from cwltool.pathmapper import PathMapper, normalizeFilesDirs


def test_subclass():
    class SubPathMapper(PathMapper):
        def __init__(self, referenced_files, basedir, stagedir, new):
            super(SubPathMapper, self).__init__(referenced_files, basedir, stagedir)
            self.new = new

    pathmap = SubPathMapper([], '', '', 'new')
    assert pathmap.new is not None, 'new'

normalization_parameters = [
    ('strip trailing slashes',
     {'class': 'Directory',
      'location': '/foo/bar/'
      },
     {'class': 'Directory',
      'location': '/foo/bar',
      'basename': 'bar'
      }
     ),
    ('file',
     {'class': 'File',
      'location': 'file1.txt'
      },
     {'class': 'File',
      'location': 'file1.txt',
      'basename': 'file1.txt',
      'nameext': '.txt',
      'nameroot': 'file1'
      }
     ),
    ('file with local uri',
     {'class': 'File',
      'location': 'file:///foo/file1.txt'
      },
     {'class': 'File',
      'location': 'file:///foo/file1.txt',
      'basename': 'file1.txt',
      'nameext': '.txt',
      'nameroot': 'file1'
      }
     ),
    ('file with http url',
     {'class': 'File',
      'location': 'http://example.com/file1.txt'
      },
     {'class': 'File',
      'location': 'http://example.com/file1.txt',
      'basename': 'file1.txt',
      'nameext': '.txt',
      'nameroot': 'file1'
      }
     )
]

@pytest.mark.parametrize('name,file_dir,expected', normalization_parameters)
def test_normalizeFilesDirs(name, file_dir, expected):
    normalizeFilesDirs(file_dir)
    assert file_dir == expected, name

# (filename, expected: (nameroot, nameext))
basename_generation_parameters = [
    ('foo.bar', ('foo', '.bar')),
    ('foo', ('foo', '')),
    ('.foo', ('.foo', '')),
    ('foo.', ('foo', '.')),
    ('foo.bar.baz', ('foo.bar', '.baz'))
]
@pytest.mark.parametrize('filename,expected', basename_generation_parameters)
def test_basename_field_generation(filename, expected):
    nameroot, nameext = expected
    expected = {
        'class': 'File',
        'location': '/foo/' + filename,
        'basename': filename,
        'nameroot': nameroot,
        'nameext': nameext
    }

    file = {
        'class': 'File',
        'location': '/foo/' + filename
    }

    normalizeFilesDirs(file)
    assert file == expected
