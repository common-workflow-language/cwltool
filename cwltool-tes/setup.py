#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages


# if python3 runtime and `setup.py install` is called
if sys.version_info.major == 3 and sys.argv[1] == 'install':
    print("Aborting installation. CWL Tool doesn't support Python 3 currently.")
    print("Install using Python 2 pip.")
    exit(1)

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.md')

setup(
    name='cwltool-tes',
    version='0.1',
    description='Common workflow language reference implementation backended \
    by a GA4GH Task Execution Service',
    long_description=open(README).read(),
    author='Common workflow language working group',
    author_email='common-workflow-language@googlegroups.com',
    url="https://github.com/common-workflow-language/cwltool-tes",
    download_url="https://github.com/common-workflow-language/cwltool-tes",
    license='Apache 2.0',
    install_requires=[
        'cwltool==1.0.20170516234254'
    ],
    entry_points={
        'console_scripts': ["cwltool-tes=cwltool_tes.main:main"]},
    zip_safe=True
)
