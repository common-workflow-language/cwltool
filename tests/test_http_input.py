import os
import tempfile

from cwltool.pathmapper import PathMapper


def test_http_path_mapping():
    class SubPathMapper(PathMapper):
        def __init__(self, referenced_files, basedir, stagedir):
            super(SubPathMapper, self).__init__(referenced_files, basedir, stagedir)
    input_file_path = "https://raw.githubusercontent.com/common-workflow-language/cwltool/master/tests/2.fasta"
    tempdir = tempfile.mkdtemp()
    base_file = [{
        "class": "File",
        "location": "https://raw.githubusercontent.com/common-workflow-language/cwltool/master/tests/2.fasta",
        "basename": "chr20.fa"
    }]
    pathmap = SubPathMapper(base_file, os.getcwd(), tempdir)._pathmap

    assert input_file_path in pathmap
    assert os.path.exists(pathmap[input_file_path].resolved)

    with open(pathmap[input_file_path].resolved) as file:
        contents = file.read()

    assert ">Sequence 561 BP; 135 A; 106 C; 98 G; 222 T; 0 other;" in contents
