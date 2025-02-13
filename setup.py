#!/usr/bin/env python3
"""Setup for the reference implementation of the CWL standards."""
import glob
import os
import sys
import warnings
from typing import TYPE_CHECKING, Any

from setuptools import Extension, setup

if TYPE_CHECKING:
    from typing_extensions import TypeGuard

if os.name == "nt":
    warnings.warn(
        "The CWL reference runner (cwltool) no longer supports running "
        "CWL workflows natively on MS Windows as its previous MS Windows "
        "support was incomplete and untested. Instead, please see "
        "https://pypi.org/project/cwltool/#ms-windows-users "
        "for instructions on running cwltool via "
        "Windows Subsystem for Linux 2 (WSL2). If don't need to execute "
        "CWL documents, then you can ignore this warning, but please "
        "consider migrating to https://pypi.org/project/cwl-utils/ "
        "for your CWL document processing needs.",
        stacklevel=1,
    )


def _is_list_of_setuptools_extension(items: list[Any]) -> "TypeGuard[list[Extension]]":
    return all(isinstance(item, Extension) for item in items)


def _find_package_data(base: str, globs: list[str], root: str = "cwltool") -> list[str]:
    """
    Find all interesting data files, for setup(package_data=).

    Arguments:
      root:  The directory to search in.
      globs: A list of glob patterns to accept files.
    """
    rv_dirs = [root for root, dirs, files in os.walk(base)]
    rv = []
    for rv_dir in rv_dirs:
        files = []
        for pat in globs:
            files += glob.glob(os.path.join(rv_dir, pat))
        if not files:
            continue
        rv.extend([os.path.relpath(f, root) for f in files])
    return rv


SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, "README.rst")

NEEDS_PYTEST = {"pytest", "test", "ptr"}.intersection(sys.argv)
PYTEST_RUNNER = ["pytest-runner", "pytest-cov"] if NEEDS_PYTEST else []
USE_MYPYC = False
# To compile with mypyc, a mypyc checkout must be present on the PYTHONPATH
if len(sys.argv) > 1 and sys.argv[1] == "--use-mypyc":
    sys.argv.pop(1)
    USE_MYPYC = True
if os.getenv("CWLTOOL_USE_MYPYC", None) == "1":
    USE_MYPYC = True

if USE_MYPYC:
    mypyc_skiplist = tuple(
        os.path.join("cwltool", x)
        for x in (
            "context.py",  # monkeypatching
            "__init__.py",
            "loghandler.py",  # so we can monkeypatch the logger from tests
            "__main__.py",
            "cwlprov/__init__.py",
            "cuda.py",  # for monkeypatch
            "run_job.py",
            "cwlprov/writablebagfile.py",  # WritableBag is having issues
            "stdfsaccess.py",  # StdFsAccess needs to be subclassable
        )
    )

    everything = [os.path.join("cwltool", x) for x in _find_package_data("cwltool", ["*.py"])]
    # Start with all the .py files
    all_real_pys = [
        x for x in everything if not x.startswith(os.path.join("mypy", "typeshed") + os.sep)
    ]
    # Strip out anything in our skiplist
    mypyc_targets = [x for x in all_real_pys if x not in mypyc_skiplist]

    # Strip out any test code
    mypyc_targets = [x for x in mypyc_targets if not x.startswith(("tests" + os.sep))]

    mypyc_targets.sort()

    from mypyc.build import mypycify

    opt_level = os.getenv("MYPYC_OPT_LEVEL", "3")
    debug_level = os.getenv("MYPYC_DEBUG_LEVEL", "1")
    force_multifile = os.getenv("MYPYC_MULTI_FILE", "") == "1"
    ext_modules = mypycify(
        mypyc_targets,
        opt_level=opt_level,
        debug_level=debug_level,
        multi_file=force_multifile,
    )
else:
    ext_modules = []

assert _is_list_of_setuptools_extension(ext_modules), "Expected mypycify to use setuptools"

setup(
    name="cwltool",
    description="Common workflow language reference implementation",
    long_description=open(README).read(),
    long_description_content_type="text/x-rst",
    author="Common workflow language working group",
    author_email="common-workflow-language@googlegroups.com",
    url="https://github.com/common-workflow-language/cwltool",
    download_url="https://github.com/common-workflow-language/cwltool",
    ext_modules=ext_modules,
    # platforms='',  # empty as is conveyed by the classifier below
    # license='',  # empty as is conveyed by the classifier below
    packages=[
        "cwltool",
        "cwltool.cwlprov",
        "cwltool.jshint",
        "cwltool.rdfqueries",
        "cwltool.schemas",
        "cwltool.tests",
        "cwltool.tests.checker_wf",
        "cwltool.tests.input_deps",
        "cwltool.tests.loop",
        "cwltool.tests.override",
        "cwltool.tests.reloc",
        "cwltool.tests.subgraph",
        "cwltool.tests.test_deps_env",
        "cwltool.tests.test_deps_env.modulefiles",
        "cwltool.tests.tmp1.tmp2.tmp3",
        "cwltool.tests.tmp4.alpha",
        "cwltool.tests.trs",
        "cwltool.tests.wf",
        "cwltool.tests.wf.generator",
        "cwltool.tests.wf.indir",
        "cwltool.tests.wf.operation",
    ],
    package_dir={"cwltool.tests": "tests"},
    include_package_data=True,
    install_requires=[
        "requests >= 2.6.1",  # >= 2.6.1 to workaround
        # https://github.com/ionrock/cachecontrol/issues/137
        "ruamel.yaml >= 0.16, < 0.19",
        "rdflib >= 4.2.2, < 7.2.0",
        "schema-salad >= 8.7, < 9",
        "prov == 1.5.1",
        "mypy-extensions",
        "psutil >= 5.6.6",
        "coloredlogs",
        "pydot >= 1.4.1, <3",
        "argcomplete >= 1.12.0",
        "pyparsing != 3.0.2",  # breaks --print-dot (pydot) https://github.com/pyparsing/pyparsing/issues/319
        "cwl-utils >= 0.32",
        "spython >= 0.3.0",
        "rich-argparse",
    ],
    extras_require={
        "deps": [
            "galaxy-tool-util>=22.1.2,!=23.0.1,!=23.0.2,!=23.0.3,!=23.0.4,!=23.0.5,<24.3",
            "galaxy-util <24.3",
        ],
    },
    python_requires=">=3.9, <3.14",
    use_scm_version=True,
    setup_requires=PYTEST_RUNNER + ["setuptools_scm>=8.0.4,<9"],
    test_suite="tests",
    tests_require=[
        "bagit >= 1.6.4, < 1.9",
        "pytest >= 6.2, < 8.4",
        "mock >= 2.0.0",
        "pytest-mock >= 1.10.0",
        "pytest-httpserver",
        "arcp >= 0.2.0",
    ],
    entry_points={"console_scripts": ["cwltool=cwltool.main:run"]},
    zip_safe=True,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Astronomy",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: System :: Distributed Computing",
        "Topic :: Utilities",
    ],
)
